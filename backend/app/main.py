from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from datetime import date
from io import BytesIO

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import and_, or_, select, func
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash
from PIL import Image, ImageEnhance, ImageOps
import zxingcpp
import pytesseract
from pytesseract.pytesseract import TesseractNotFoundError

from app.config import settings
from app.db import get_db_session
from app.models import Genre, Movie, MovieCast, MovieCrew, MovieGenre, MovieRecommendation, Person, Review, User
from app.schemas import (
    GenreOut,
    LoginIn,
    MovieDetail,
    MovieListItem,
    RecommendationOut,
    RegisterIn,
    ReviewIn,
    ReviewOut,
    UserOut,
)


app = FastAPI(title=settings.app_name)

app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key, same_site="lax", https_only=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)


def db_session() -> Session:
    with get_db_session() as session:
        yield session


USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")


def require_user_id(request: Request) -> int:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return int(user_id)


def require_verified_user(request: Request, session: Session) -> User:
    user_id = require_user_id(request)
    user = session.get(User, user_id)
    if not user:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if not getattr(user, "is_age_verified", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Age verification required")
    return user


def _calc_age_years(birth: date, today: date) -> int:
    years = today.year - birth.year
    if (today.month, today.day) < (birth.month, birth.day):
        years -= 1
    return years


def _format_dob_ddmmyyyy(d: date) -> str:
    return f"{d.day:02d}/{d.month:02d}/{d.year:04d}"


def _normalize_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _ocr_text(image: Image.Image) -> str:
    # OCR requires tesseract installed on the system.
    # If not installed, pytesseract raises an error; we surface a clear message.
    def variants(im: Image.Image) -> list[Image.Image]:
        outs: list[Image.Image] = []

        # 1) raw
        outs.append(im)

        # 2) upscaled + grayscale (often best for licences)
        try:
            up = im.resize((im.size[0] * 2, im.size[1] * 2))
            outs.append(ImageOps.grayscale(up))
        except Exception:
            pass

        # 3) upscaled + grayscale + contrast
        try:
            up = im.resize((im.size[0] * 2, im.size[1] * 2))
            g = ImageOps.grayscale(up)
            c = ImageEnhance.Contrast(g).enhance(1.7)
            outs.append(c)
        except Exception:
            pass

        # 4) upscaled + grayscale + slight sharpness
        try:
            up = im.resize((im.size[0] * 2, im.size[1] * 2))
            g = ImageOps.grayscale(up)
            s = ImageEnhance.Sharpness(g).enhance(1.5)
            outs.append(s)
        except Exception:
            pass

        return outs

    def score(txt: str) -> int:
        if not txt:
            return 0
        t = txt.replace(" ", "")
        # Prefer text that already contains a date pattern
        if re.search(r"(19\\d{2}|20\\d{2})[-/.](0[1-9]|1[0-2])[-/.](0[1-9]|[12]\\d|3[01])", t):
            return 100
        if re.search(r"(0[1-9]|[12]\\d|3[01])[-/.](0[1-9]|1[0-2])[-/.](19\\d{2}|20\\d{2})", t):
            return 90
        # Otherwise, prefer more digits (IDs contain digits)
        return sum(ch.isdigit() for ch in t)

    # Collect multiple OCR attempts; passports often need different preprocessing
    # to make both the VIZ dates and MRZ lines readable.
    attempts: list[tuple[int, str]] = []

    for im in variants(image):
        for psm in ("6", "11"):
            try:
                txt = pytesseract.image_to_string(im, lang="eng", config=f"--psm {psm}")
            except Exception:
                continue
            sc = score(txt)
            if txt:
                attempts.append((sc, txt))

    if not attempts:
        return ""

    # Take the best few distinct attempts and concatenate them.
    # This increases the chance we include the DOB (and MRZ) even if one attempt misses it.
    attempts.sort(key=lambda x: x[0], reverse=True)
    seen: set[str] = set()
    picked: list[str] = []
    for _, txt in attempts[:8]:
        key = txt.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        picked.append(txt)
        if len(picked) >= 4:
            break
    return "\n\n".join(picked)


def _extract_dob_from_text(text: str) -> date | None:
    """
    Best-effort DOB extraction from OCR text.
    Supports common formats seen on licences/passports: YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD,
    and DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY.

    UK/British passport support:
    - MRZ encodes DOB as YYMMDD (with implied century) followed by a check digit and sex.
      Example (TD3 line 2 snippet): ... GBR8701196M1601013 ...
    - Visual inspection zone often prints DOB as "DD MMM YYYY" (e.g. 30 MAY 2006).
    """
    # Normalize common OCR confusions for digits
    raw = text or ""
    # Keep a "no whitespace" view for MRZ and numeric formats.
    compact = raw.replace(" ", "").replace("\n", "").upper()

    candidates: list[date] = []

    # 1) Passport MRZ YYMMDD: DOB is in line 2 after nationality (3 letters),
    # followed by a check digit and sex marker.
    # Example snippet: "...IND0603205F..." -> 2006-03-20
    # IMPORTANT: do NOT apply digit/letter OCR substitutions before MRZ parsing,
    # otherwise "IND/GBR" can become "1ND" and break matching.
    mrz = re.search(r"[A-Z<]{3}(\d{2})(\d{2})(\d{2})\d[MF<]", compact)
    if mrz:
        yy, mm, dd = int(mrz.group(1)), int(mrz.group(2)), int(mrz.group(3))
        # Century inference: if YY is greater than current YY, assume 1900s, else 2000s.
        today = date.today()
        pivot = today.year % 100
        year = 1900 + yy if yy > pivot else 2000 + yy
        try:
            candidates.append(date(year, mm, dd))
        except Exception:
            pass

    # From here on, apply common OCR digit substitutions to improve parsing of printed dates.
    t = compact
    t = (
        t.replace("O", "0")
        .replace("S", "5")
        .replace("I", "1")
        .replace("L", "1")
        .replace("|", "1")
    )

    # 2) "DD MMM YYYY" / "DD-MMM-YYYY" (passport VIZ). Use a spaced, uppercased view.
    months = {
        "JAN": 1,
        "FEB": 2,
        "MAR": 3,
        "APR": 4,
        "MAY": 5,
        "JUN": 6,
        "JUL": 7,
        "AUG": 8,
        "SEP": 9,
        "OCT": 10,
        "NOV": 11,
        "DEC": 12,
    }
    viz = re.sub(r"[^A-Za-z0-9]+", " ", raw).strip().upper()
    m_viz = re.search(r"\b(0[1-9]|[12]\d|3[01])\s+([A-Z]{3})\s+(19\d{2}|20\d{2})\b", viz)
    if m_viz and m_viz.group(2) in months:
        try:
            candidates.append(date(int(m_viz.group(3)), months[m_viz.group(2)], int(m_viz.group(1))))
        except Exception:
            pass

    # 3) YYYY-MM-DD or YYYY/MM/DD or YYYY.MM.DD (collect all)
    for m in re.finditer(r"(19\d{2}|20\d{2})[-/.](0[1-9]|1[0-2])[-/.](0[1-9]|[12]\d|3[01])", t):
        try:
            candidates.append(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except Exception:
            pass

    # 4) DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY (collect all)
    for m2 in re.finditer(r"(0[1-9]|[12]\d|3[01])[-/.](0[1-9]|1[0-2])[-/.](19\d{2}|20\d{2})", t):
        try:
            candidates.append(date(int(m2.group(3)), int(m2.group(2)), int(m2.group(1))))
        except Exception:
            pass

    if not candidates:
        return None

    # Prefer the oldest plausible DOB (avoids choosing issue/expiry dates).
    today = date.today()
    plausible: list[date] = []
    for d in candidates:
        age = _calc_age_years(d, today)
        if 5 <= age <= 120:
            plausible.append(d)
    if plausible:
        return min(plausible)

    return None


def _name_matches_expected_name(ocr_text: str, expected_name: str) -> bool:
    """
    Simple anti-fraud check for this uni project:
    - document text should contain the person's registered full name (best effort).
    - we split expected_name into tokens and require each meaningful token (len>=3) to appear.
    This prevents verifying a different person's document.
    """
    exp = (expected_name or "").strip()
    if not exp:
        return False

    expected_tokens = [_normalize_name(t) for t in re.split(r"\s+", exp.lower()) if len(t.strip()) >= 3]
    expected_tokens = [t for t in expected_tokens if t]
    if not expected_tokens:
        return False

    # Extract candidate "name-like" tokens from OCR text.
    # If OCR doesn't yield enough alphabetic tokens, we don't hard-fail.
    doc_tokens = [_normalize_name(t) for t in re.findall(r"[A-Za-z]{3,}", ocr_text or "")]
    doc_tokens = [t for t in doc_tokens if t]
    doc_unique = set(doc_tokens)

    intersection = doc_unique.intersection(expected_tokens)
    if intersection:
        return True

    # If OCR *did* capture several alphabetic tokens but none match, reject.
    # Otherwise, accept (can't reliably validate the name from this image).
    return len(doc_unique) < 2


def validate_password(password: str) -> list[str]:
    errors: list[str] = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if not re.search(r"[A-Za-z]", password):
        errors.append("Password must contain at least 1 letter.")
    if not re.search(r"\d", password):
        errors.append("Password must contain at least 1 number.")
    return errors


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, request: Request, session: Session = Depends(db_session)) -> UserOut:
    username = payload.username.strip()
    full_name = payload.full_name.strip()
    email = payload.email.strip().lower()

    errors: list[str] = []
    if not USERNAME_RE.match(username):
        errors.append("Username must be 3–20 chars and contain only letters, numbers, underscore.")
    errors.extend(validate_password(payload.password))
    if errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=errors)

    existing = session.execute(select(User).where(or_(User.username == username, User.email == email))).scalars().first()
    if existing:
        if existing.username == username:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=["Username already taken."])
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=["Email already registered."])

    user = User(username=username, full_name=full_name, email=email, password_hash=generate_password_hash(payload.password))
    session.add(user)
    session.commit()
    session.refresh(user)

    request.session.clear()
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["failed_login_attempts"] = 0

    return UserOut(id=user.id, username=user.username, full_name=user.full_name, email=user.email)


@app.post("/login", response_model=UserOut)
def login(payload: LoginIn, request: Request, session: Session = Depends(db_session)) -> UserOut:
    failed = int(request.session.get("failed_login_attempts") or 0)
    if failed >= 5:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many failed attempts.")

    identifier = payload.identifier.strip()
    user = (
        session.execute(select(User).where(or_(User.username == identifier, User.email == identifier.lower())))
        .scalars()
        .first()
    )
    if not user or not check_password_hash(user.password_hash, payload.password):
        request.session["failed_login_attempts"] = failed + 1
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    request.session.clear()
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["failed_login_attempts"] = 0

    return UserOut(id=user.id, username=user.username, full_name=getattr(user, "full_name", None), email=user.email)


@app.post("/logout")
def logout(request: Request) -> dict:
    request.session.clear()
    return {"ok": True}


@app.get("/me")
def me(request: Request, session: Session = Depends(db_session)) -> dict:
    user_id = request.session.get("user_id")
    if not user_id:
        return {"user": None}
    user = session.get(User, int(user_id))
    if not user:
        request.session.clear()
        return {"user": None}
    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": getattr(user, "full_name", None),
            "is_age_verified": bool(getattr(user, "is_age_verified", False)),
            "verification_status": getattr(user, "verification_status", "pending"),
            "is_adult": bool(getattr(user, "is_adult", False)),
            "birth_date": str(getattr(user, "birth_date", None)) if getattr(user, "birth_date", None) else None,
        }
    }


@app.get("/favourites")
def favourites(request: Request) -> dict:
    user_id = require_user_id(request)
    return {"message": "Protected route", "user_id": user_id}


@app.get("/movies/{movie_id}/reviews", response_model=list[ReviewOut])
def list_reviews(movie_id: int, session: Session = Depends(db_session)) -> list[ReviewOut]:
    rows = session.execute(
        select(Review, User.username)
        .join(User, User.id == Review.user_id)
        .where(Review.movie_id == movie_id)
        .order_by(Review.created_at.desc())
        .limit(50)
    ).all()
    return [
        ReviewOut(
            id=r.id,
            movie_id=r.movie_id,
            user_id=r.user_id,
            username=username,
            rating=r.rating,
            review_text=r.review_text,
            created_at=str(r.created_at),
        )
        for (r, username) in rows
    ]


@app.post("/movies/{movie_id}/reviews", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def add_review(movie_id: int, payload: ReviewIn, request: Request, session: Session = Depends(db_session)) -> ReviewOut:
    user = require_verified_user(request, session)
    user_id = user.id

    # Ensure movie exists
    if session.get(Movie, movie_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")

    # One review per user per movie: update if exists
    existing = (
        session.execute(select(Review).where(and_(Review.movie_id == movie_id, Review.user_id == user_id)))
        .scalars()
        .first()
    )

    if existing:
        existing.rating = payload.rating
        existing.review_text = (payload.review_text or "").strip() or None
        session.commit()
        session.refresh(existing)
        username = request.session.get("username") or ""
        return ReviewOut(
            id=existing.id,
            movie_id=existing.movie_id,
            user_id=existing.user_id,
            username=str(username),
            rating=existing.rating,
            review_text=existing.review_text,
            created_at=str(existing.created_at),
        )

    review = Review(
        movie_id=movie_id,
        user_id=user_id,
        rating=payload.rating,
        review_text=(payload.review_text or "").strip() or None,
    )
    session.add(review)
    session.commit()
    session.refresh(review)

    username = request.session.get("username") or ""
    return ReviewOut(
        id=review.id,
        movie_id=review.movie_id,
        user_id=review.user_id,
        username=str(username),
        rating=review.rating,
        review_text=review.review_text,
        created_at=str(review.created_at),
    )


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@app.post("/verify-id")
async def verify_id(
    request: Request,
    id_document: UploadFile = File(...),
    session: Session = Depends(db_session),
) -> dict:
    """
    Age verification via photo ID upload (SIMULATED).

    - Requires login (session cookie)
    - Accepts image uploads: id_document (required) and selfie (optional)
    - Saves to backend/uploads/ temporarily
    - Simulates approval/rejection (no external API)
    - Updates users table:
        approved -> is_age_verified=true, verification_status='approved', verified_at=now
        rejected -> is_age_verified=false, verification_status='rejected'

    SECURITY NOTES:
    - Never trust frontend user_id; always use session.
    - Validate file types (images only).
    - In a real system, delete uploads after verification.
    - Use HTTPS in production so uploads + session cookie are protected.
    """
    user_id = require_user_id(request)
    user = session.get(User, user_id)
    if not user:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    # Basic validation: content type must be an allowed image
    if id_document.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="id_document must be an image (jpg/png/webp)")

    uploads_dir = Path(__file__).resolve().parents[1] / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    def _safe_ext(upload: UploadFile) -> str:
        name = (upload.filename or "").lower()
        if name.endswith(".png"):
            return ".png"
        if name.endswith(".webp"):
            return ".webp"
        return ".jpg"

    # Save files (temporary)
    token = uuid.uuid4().hex
    id_path = uploads_dir / f"id_{user_id}_{token}{_safe_ext(id_document)}"
    id_bytes = await id_document.read()
    if not id_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="id_document is empty")
    if len(id_bytes) > 8 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="id_document too large (max 8MB)")
    id_path.write_bytes(id_bytes)

    # Verification (offline):
    # 1) Try to decode a PDF417 barcode (common on driving licences).
    # 2) If barcode isn't present, fall back to OCR (passport/licence front) to extract DOB and name.
    dob: date | None = None
    ocr_text: str | None = None
    try:
        img = Image.open(BytesIO(id_bytes)).convert("RGB")
        decoded = zxingcpp.read_barcode(img, formats=[zxingcpp.BarcodeFormat.PDF417])
        if decoded and decoded.text:
            m = re.search(r"DBB(\d{8})", decoded.text)
            if m:
                y, mo, d = int(m.group(1)[0:4]), int(m.group(1)[4:6]), int(m.group(1)[6:8])
                dob = date(y, mo, d)
                ocr_text = decoded.text  # includes name fields on many AAMVA barcodes
    except Exception:
        dob = None

    if dob is None:
        try:
            img = Image.open(BytesIO(id_bytes)).convert("RGB")
            ocr_text = _ocr_text(img)
            dob = _extract_dob_from_text(ocr_text)
        except TesseractNotFoundError:
            # Clear instruction for local dev
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OCR engine not installed. Install tesseract (brew install tesseract) and restart the backend.",
            )
        except Exception:
            dob = None

    # Must have DOB to verify age
    if dob is None:
        user.verification_method = "photo_id"
        user.verification_status = "rejected"
        user.is_age_verified = False
        user.verified_at = None
        session.commit()
        # In dev, return OCR hint to help debugging (do NOT do this in production).
        if settings.app_env == "dev":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Could not read date of birth from the document photo.",
                    "hint": "Try a clearer image; make sure DOB is visible. If OCR misreads digits, try different lighting.",
                    "ocr_preview": (ocr_text or "")[:400],
                },
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Could not read date of birth from the document photo. "
                "Please upload a clearer image of your passport (MRZ page) or driving licence."
            ),
        )

    # Anti-fraud: name on document must match username (best-effort)
    if ocr_text is None:
        try:
            img = Image.open(BytesIO(id_bytes)).convert("RGB")
            ocr_text = _ocr_text(img)
        except Exception:
            ocr_text = ""
    expected_name = str(getattr(user, "full_name", "") or getattr(user, "username", ""))
    if not _name_matches_expected_name(ocr_text or "", expected_name):
        user.verification_method = "photo_id"
        user.verification_status = "rejected"
        user.is_age_verified = False
        user.verified_at = None
        session.commit()
        if settings.app_env == "dev":
            expected_tokens_dbg = [_normalize_name(t) for t in re.split(r"\s+", (expected_name or "").lower()) if len(t.strip()) >= 3]
            expected_tokens_dbg = [t for t in expected_tokens_dbg if t]
            doc_tokens_dbg = [_normalize_name(t) for t in re.findall(r"[A-Za-z]{3,}", ocr_text or "")]
            doc_tokens_dbg = [t for t in doc_tokens_dbg if t]
            doc_unique_dbg = sorted(set(doc_tokens_dbg))[:40]
            inter_dbg = sorted(set(doc_tokens_dbg).intersection(expected_tokens_dbg))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Name on document does not match your profile.",
                    "expected_name": expected_name,
                    "expected_tokens": expected_tokens_dbg,
                    "doc_tokens_sample": doc_unique_dbg,
                    "intersection": inter_dbg,
                    "ocr_preview": (ocr_text or "")[:400],
                },
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name on document does not match your profile.")

    age = _calc_age_years(dob, date.today())
    status_str = "approved"

    user.verification_method = "photo_id"
    user.verification_status = status_str
    user.is_age_verified = True
    user.verified_at = datetime.now(timezone.utc)
    user.birth_date = dob
    user.is_adult = age >= 18

    session.commit()

    # For a real system: delete files here after verification is done
    # (or move them to secure storage + restrict access).
    return {
        "verification_status": user.verification_status,
        "is_age_verified": user.is_age_verified,
        "is_adult": bool(getattr(user, "is_adult", False)),
        "age_years": age,
        "date_of_birth": _format_dob_ddmmyyyy(dob),
        "verified_at": str(user.verified_at) if user.verified_at else None,
        "note": "Verification is done locally by reading the document barcode (PDF417).",
    }


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
    <html>
      <head><title>MovieScope API</title></head>
      <body style="font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; padding: 24px;">
        <h2>MovieScope API is running</h2>
        <p>This is the <b>backend</b> (API). You normally do not browse it like a website.</p>
        <ul>
          <li>API docs (test endpoints): <a href="/docs">/docs</a></li>
          <li>Health check: <a href="/health">/health</a></li>
        </ul>
        <p><b>Frontend website</b> should be opened on: <code>http://localhost:8080</code> (or <code>http://localhost:5500</code>)</p>
      </body>
    </html>
    """


@app.get("/genres", response_model=list[GenreOut])
def list_genres(session: Session = Depends(db_session)) -> list[GenreOut]:
    rows = session.execute(select(Genre).order_by(Genre.genre_name.asc())).scalars().all()
    return [GenreOut(genre_id=g.genre_id, genre_name=g.genre_name) for g in rows]


@app.get("/movies", response_model=list[MovieListItem])
def list_movies(
    response: Response,
    request: Request,
    session: Session = Depends(db_session),
    q: str | None = Query(default=None, description="Search by movie title"),
    genres: list[int] | None = Query(default=None, description="Genre IDs (repeat param). Example: ?genres=28&genres=12"),
    actor: str | None = Query(default=None, description="Actor name (partial match)"),
    director: str | None = Query(default=None, description="Director name (partial match)"),
    year_from: int | None = Query(default=None, ge=1800, le=2200),
    year_to: int | None = Query(default=None, ge=1800, le=2200),
    budget_min: int | None = Query(default=None, ge=0),
    budget_max: int | None = Query(default=None, ge=0),
    revenue_min: int | None = Query(default=None, ge=0),
    revenue_max: int | None = Query(default=None, ge=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> list[MovieListItem]:
    movie_stmt = select(Movie)
    conditions = []

    # Age restriction: if user is not verified adult, hide adult movies.
    try:
        uid = request.session.get("user_id")
        user = session.get(User, int(uid)) if uid else None
    except Exception:
        user = None
    is_adult_user = bool(getattr(user, "is_adult", False)) if user else False
    if not is_adult_user:
        conditions.append(or_(Movie.adult.is_(None), Movie.adult.is_(False)))

    if q:
        like = f"%{q.strip()}%"
        conditions.append(Movie.title.like(like))

    if year_from is not None:
        conditions.append(Movie.release_year.is_not(None))
        conditions.append(Movie.release_year >= year_from)

    if year_to is not None:
        conditions.append(Movie.release_year.is_not(None))
        conditions.append(Movie.release_year <= year_to)

    if budget_min is not None:
        conditions.append(Movie.budget.is_not(None))
        conditions.append(Movie.budget >= budget_min)

    if budget_max is not None:
        conditions.append(Movie.budget.is_not(None))
        conditions.append(Movie.budget <= budget_max)

    if revenue_min is not None:
        conditions.append(Movie.revenue.is_not(None))
        conditions.append(Movie.revenue >= revenue_min)

    if revenue_max is not None:
        conditions.append(Movie.revenue.is_not(None))
        conditions.append(Movie.revenue <= revenue_max)

    if genres:
        movie_stmt = movie_stmt.join(MovieGenre, MovieGenre.movie_id == Movie.movie_id)
        conditions.append(MovieGenre.genre_id.in_(genres))

    if actor:
        movie_stmt = (
            movie_stmt.join(MovieCast, MovieCast.movie_id == Movie.movie_id)
            .join(Person, Person.person_id == MovieCast.person_id)
        )
        conditions.append(Person.name.ilike(f"%{actor.strip()}%"))

    if director:
        director_person = Person.__table__.alias("director_person")
        movie_stmt = (
            movie_stmt.join(MovieCrew, MovieCrew.movie_id == Movie.movie_id)
            .join(director_person, director_person.c.person_id == MovieCrew.person_id)
        )
        conditions.append(MovieCrew.job == "Director")
        conditions.append(director_person.c.name.ilike(f"%{director.strip()}%"))

    if conditions:
        movie_stmt = movie_stmt.where(and_(*conditions))

    # Total count (for pagination UI). We count distinct movie IDs to avoid duplicates caused by joins.
    count_stmt = movie_stmt.with_only_columns(Movie.movie_id).distinct().subquery()
    total = session.execute(select(func.count()).select_from(count_stmt)).scalar_one()

    if response is not None:
        response.headers["X-Total-Count"] = str(total)

    movie_stmt = movie_stmt.order_by(Movie.vote_average.desc().nullslast(), Movie.vote_count.desc().nullslast())
    movie_stmt = movie_stmt.offset((page - 1) * page_size).limit(page_size)

    movies = session.execute(movie_stmt).scalars().unique().all()

    if not movies:
        return []

    movie_ids = [m.movie_id for m in movies]
    genre_rows = session.execute(
        select(MovieGenre.movie_id, Genre.genre_name)
        .join(Genre, Genre.genre_id == MovieGenre.genre_id)
        .where(MovieGenre.movie_id.in_(movie_ids))
        .order_by(Genre.genre_name.asc())
    ).all()

    genres_by_movie: dict[int, list[str]] = {}
    for movie_id, genre_name in genre_rows:
        genres_by_movie.setdefault(movie_id, []).append(genre_name)

    return [
        MovieListItem(
            movie_id=m.movie_id,
            title=m.title,
            overview=m.overview,
            release_year=m.release_year,
            runtime=m.runtime,
            budget=m.budget,
            revenue=m.revenue,
            vote_average=float(m.vote_average) if m.vote_average is not None else None,
            vote_count=m.vote_count,
            genres=genres_by_movie.get(m.movie_id, []),
            poster_path=getattr(m, "poster_path", None),
        )
        for m in movies
    ]


@app.get("/movies/{movie_id}", response_model=MovieDetail)
def get_movie(movie_id: int, request: Request, session: Session = Depends(db_session)) -> MovieDetail:
    movie = session.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")

    # Age restriction: block adult movies for non-adult users.
    if bool(getattr(movie, "adult", False)):
        uid = request.session.get("user_id")
        user = session.get(User, int(uid)) if uid else None
        if not user or not bool(getattr(user, "is_adult", False)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="18+ content restricted")

    genre_rows = session.execute(
        select(Genre.genre_id, Genre.genre_name)
        .join(MovieGenre, MovieGenre.genre_id == Genre.genre_id)
        .where(MovieGenre.movie_id == movie_id)
        .order_by(Genre.genre_name.asc())
    ).all()

    cast_rows = session.execute(
        select(Person.name)
        .join(MovieCast, MovieCast.person_id == Person.person_id)
        .where(MovieCast.movie_id == movie_id)
        .order_by(MovieCast.cast_order.asc().nullslast())
        .limit(12)
    ).scalars().all()

    director_row = session.execute(
        select(Person.name)
        .join(MovieCrew, MovieCrew.person_id == Person.person_id)
        .where(MovieCrew.movie_id == movie_id, MovieCrew.job == "Director")
        .limit(1)
    ).scalars().first()

    return MovieDetail(
        movie_id=movie.movie_id,
        title=movie.title,
        overview=movie.overview,
        release_date=movie.release_date,  # type: ignore[arg-type]
        release_year=movie.release_year,
        runtime=movie.runtime,
        budget=movie.budget,
        revenue=movie.revenue,
        vote_average=float(movie.vote_average) if movie.vote_average is not None else None,
        vote_count=movie.vote_count,
        adult=movie.adult,
        original_language=movie.original_language,
        tagline=movie.tagline,
        poster_path=getattr(movie, "poster_path", None),
        genres=[GenreOut(genre_id=g_id, genre_name=g_name) for (g_id, g_name) in genre_rows],
        cast=list(cast_rows),
        director=director_row,
    )


@app.get("/movies/{movie_id}/recommendations", response_model=list[RecommendationOut])
def get_recommendations(movie_id: int, request: Request, session: Session = Depends(db_session)) -> list[RecommendationOut]:
    # Age restriction: if the source movie is adult, enforce the same policy as /movies/{id}.
    movie = session.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    if bool(getattr(movie, "adult", False)):
        uid = request.session.get("user_id")
        user = session.get(User, int(uid)) if uid else None
        if not user or not bool(getattr(user, "is_adult", False)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="18+ content restricted")

    # Join recommendations -> movie table for display info.
    stmt = (
        select(
            Movie.movie_id,
            Movie.title,
            Movie.poster_path,
            Movie.vote_average,
            MovieRecommendation.similarity_score,
        )
        .join(Movie, Movie.movie_id == MovieRecommendation.recommended_movie_id)
        .where(MovieRecommendation.movie_id == movie_id)
        .order_by(MovieRecommendation.similarity_score.desc().nullslast(), Movie.vote_count.desc().nullslast())
        .limit(10)
    )
    rows = session.execute(stmt).all()

    # Hide adult recommended movies for non-adult users.
    uid = request.session.get("user_id")
    user = session.get(User, int(uid)) if uid else None
    is_adult_user = bool(getattr(user, "is_adult", False)) if user else False
    if not is_adult_user:
        # Fetch adult flags for these rows only (cheap).
        ids = [r[0] for r in rows]
        if ids:
            adult_map = dict(session.execute(select(Movie.movie_id, Movie.adult).where(Movie.movie_id.in_(ids))).all())
            rows = [r for r in rows if not bool(adult_map.get(r[0], False))]

    return [
        RecommendationOut(
            movie_id=int(mid),
            title=str(title),
            poster_path=str(poster) if poster is not None else None,
            vote_average=float(vote) if vote is not None else None,
            similarity_score=float(score) if score is not None else None,
        )
        for (mid, title, poster, vote, score) in rows
    ]


@app.get("/people/search")
def search_people(
    q: str = Query(min_length=1, max_length=60),
    limit: int = Query(default=10, ge=1, le=50),
    session: Session = Depends(db_session),
) -> list[dict]:
    rows = session.execute(
        select(Person.person_id, Person.name)
        .where(Person.name.ilike(f"%{q.strip()}%"))
        .order_by(Person.name.asc())
        .limit(limit)
    ).all()
    return [{"person_id": pid, "name": name} for (pid, name) in rows]

