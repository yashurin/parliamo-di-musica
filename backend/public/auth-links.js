(function () {
  function addRegisterLink() {
    if (document.getElementById("pdm-register-link")) {
      return;
    }

    const isLoginPage =
      window.location.pathname.endsWith("/login") ||
      document.body.innerText.includes("Login to access the app");

    if (!isLoginPage) {
      return;
    }

    const link = document.createElement("div");
    link.id = "pdm-register-link";
    link.style.marginTop = "1rem";
    link.style.textAlign = "center";
    link.style.fontSize = "0.9rem";
    link.style.color = "#a1a1aa";
    link.innerHTML =
      'Don\u2019t have an account? <a href="/auth/register" style="color:#818cf8;text-decoration:none;">Create one</a>';

    const form = document.querySelector("form");
    if (form && form.parentElement) {
      form.parentElement.appendChild(link);
    }
  }

  const observer = new MutationObserver(addRegisterLink);
  observer.observe(document.body, { childList: true, subtree: true });
  addRegisterLink();
})();