from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from auth.schemas import RegisterRequest, RegisterResponse
from auth.user_store import user_store
from logging_config import get_logger

logger = get_logger("api")

router = APIRouter(prefix="/auth", tags=["auth"])

REGISTER_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Create account — Parliamo di Musica</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0f0f10;
      color: #f4f4f5;
    }
    .card {
      width: 100%;
      max-width: 420px;
      padding: 2rem;
      border-radius: 12px;
      background: #18181b;
      border: 1px solid #27272a;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.35);
    }
    h1 { margin: 0 0 0.5rem; font-size: 1.5rem; }
    p { margin: 0 0 1.5rem; color: #a1a1aa; font-size: 0.95rem; }
    label { display: block; margin-bottom: 0.35rem; font-size: 0.875rem; color: #d4d4d8; }
    input {
      width: 100%;
      margin-bottom: 1rem;
      padding: 0.75rem 0.9rem;
      border-radius: 8px;
      border: 1px solid #3f3f46;
      background: #09090b;
      color: #f4f4f5;
      font-size: 1rem;
    }
    input:focus { outline: 2px solid #6366f1; border-color: #6366f1; }
    button {
      width: 100%;
      padding: 0.8rem;
      border: none;
      border-radius: 8px;
      background: #6366f1;
      color: white;
      font-size: 1rem;
      font-weight: 600;
      cursor: pointer;
    }
    button:hover { background: #4f46e5; }
    button:disabled { opacity: 0.6; cursor: not-allowed; }
    .message {
      margin-bottom: 1rem;
      padding: 0.75rem 0.9rem;
      border-radius: 8px;
      font-size: 0.9rem;
      display: none;
    }
    .message.error { display: block; background: #451a1a; color: #fecaca; border: 1px solid #7f1d1d; }
    .message.success { display: block; background: #14532d; color: #bbf7d0; border: 1px solid #166534; }
    .footer { margin-top: 1.25rem; text-align: center; font-size: 0.9rem; color: #a1a1aa; }
    .footer a { color: #818cf8; text-decoration: none; }
    .footer a:hover { text-decoration: underline; }
    .hint { margin-top: -0.5rem; margin-bottom: 1rem; font-size: 0.8rem; color: #71717a; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Create account</h1>
    <p>Register with your email to save chat history and resume conversations.</p>
    <div id="message" class="message"></div>
    <form id="register-form">
      <label for="email">Email address</label>
      <input id="email" name="email" type="email" required autocomplete="email" placeholder="you@example.com" />
      <label for="password">Password</label>
      <input id="password" name="password" type="password" required autocomplete="new-password" minlength="8" />
      <p class="hint">At least 8 characters, including a letter and a number.</p>
      <label for="password_confirm">Confirm password</label>
      <input id="password_confirm" name="password_confirm" type="password" required autocomplete="new-password" minlength="8" />
      <button id="submit-btn" type="submit">Create account</button>
    </form>
    <div class="footer">
      Already have an account? <a href="/chat/login">Sign in</a>
    </div>
  </div>
  <script>
    const form = document.getElementById("register-form");
    const message = document.getElementById("message");
    const submitBtn = document.getElementById("submit-btn");

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      message.className = "message";
      message.textContent = "";
      submitBtn.disabled = true;

      const payload = {
        email: form.email.value.trim(),
        password: form.password.value,
        password_confirm: form.password_confirm.value,
      };

      try {
        const response = await fetch("/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) {
          let detail = data.detail || "Registration failed";
          if (Array.isArray(detail)) {
            detail = detail
              .map((item) => (item.msg || "Invalid input").replace("Value error, ", ""))
              .join(" ");
          }
          throw new Error(detail);
        }
        message.className = "message success";
        message.textContent = data.message + " Redirecting to sign in...";
        setTimeout(() => { window.location.href = "/chat/login"; }, 1500);
      } catch (error) {
        message.className = "message error";
        message.textContent = error.message;
        submitBtn.disabled = false;
      }
    });
  </script>
</body>
</html>"""


@router.get("/register", response_class=HTMLResponse)
async def register_page() -> str:
    return REGISTER_PAGE_HTML


@router.post("/register", response_model=RegisterResponse)
async def register_user(payload: RegisterRequest) -> RegisterResponse:
    try:
        user = await user_store.register(payload.email, payload.password)
    except ValueError as exc:
        logger.warning("Registration rejected for %r: %s", payload.email, exc)
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    logger.info("User registered: %s", user["email"])
    return RegisterResponse(
        message="Account created successfully.",
        email=user["email"],
    )