const clientId = "console";
const issuer = `${window.location.origin}/auth/realms/oryma`;
const redirectUri = `${window.location.origin}/admin/`;
const stateKey = "oryma.local-oidc.state";
const verifierKey = "oryma.local-oidc.verifier";

let accessToken;

const status = document.querySelector("#status");
const loginButton = document.querySelector("#login");
const clearButton = document.querySelector("#clear");
const enrollmentForm = document.querySelector("#enrollment");
const claimsSection = document.querySelector("#claims");
const resultSection = document.querySelector("#result");

function setStatus(message) {
  status.textContent = message;
}

function base64Url(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

function randomBase64Url(byteLength) {
  const bytes = crypto.getRandomValues(new Uint8Array(byteLength));
  return base64Url(bytes);
}

async function sha256Base64Url(value) {
  const bytes = new TextEncoder().encode(value);
  return base64Url(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)));
}

async function readJson(response) {
  const text = await response.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`Réponse JSON invalide (HTTP ${response.status}).`);
  }
}

function showTokenClaims(token) {
  const encoded = token.split(".")[1];
  if (!encoded) throw new Error("Access token JWT invalide.");
  const normalized = encoded.replaceAll("-", "+").replaceAll("_", "/");
  const binary = atob(normalized + "=".repeat((4 - normalized.length % 4) % 4));
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  const claims = JSON.parse(new TextDecoder().decode(bytes));
  const roles = claims.realm_access?.roles;
  const audience = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
  const summary = {
    azp: claims.azp,
    aud: claims.aud,
    role_admin: Array.isArray(roles) && roles.includes("admin"),
    realm_roles: roles,
    expiration: claims.exp ? new Date(claims.exp * 1000).toISOString() : null,
  };
  document.querySelector("#claims-output").textContent = JSON.stringify(summary, null, 2);
  claimsSection.hidden = false;
  if (claims.azp !== clientId || !audience.includes("admin-api") || !summary.role_admin) {
    setStatus("Le jeton est reçu, mais il manque un claim attendu ; l’API le vérifiera elle-même.");
  } else {
    setStatus("Jeton reçu : azp, audience et rôle admin attendus sont présents.");
  }
}

async function beginLogin() {
  setStatus("Préparation du flux PKCE…");
  loginButton.disabled = true;
  try {
    const discoveryResponse = await fetch(`${issuer}/.well-known/openid-configuration`, {
      cache: "no-store",
      credentials: "omit",
    });
    if (!discoveryResponse.ok) {
      throw new Error(`Découverte OIDC indisponible (HTTP ${discoveryResponse.status}).`);
    }
    const discovery = await readJson(discoveryResponse);
    if (!discovery.authorization_endpoint || !discovery.token_endpoint) {
      throw new Error("La configuration OIDC ne contient pas les endpoints attendus.");
    }

    const state = randomBase64Url(32);
    const verifier = randomBase64Url(64);
    const challenge = await sha256Base64Url(verifier);
    sessionStorage.setItem(stateKey, state);
    sessionStorage.setItem(verifierKey, verifier);
    sessionStorage.setItem("oryma.local-oidc.token-endpoint", discovery.token_endpoint);

    const authorizationUrl = new URL(discovery.authorization_endpoint);
    authorizationUrl.search = new URLSearchParams({
      client_id: clientId,
      redirect_uri: redirectUri,
      response_type: "code",
      scope: "openid profile",
      state,
      code_challenge: challenge,
      code_challenge_method: "S256",
    });
    window.location.assign(authorizationUrl);
  } catch (error) {
    loginButton.disabled = false;
    setStatus(error instanceof Error ? error.message : "Échec de la préparation OIDC.");
  }
}

async function finishLogin() {
  const callback = new URL(window.location.href);
  const code = callback.searchParams.get("code");
  const returnedState = callback.searchParams.get("state");
  const oidcError = callback.searchParams.get("error");
  if (!code && !oidcError) return;

  const expectedState = sessionStorage.getItem(stateKey);
  const verifier = sessionStorage.getItem(verifierKey);
  const tokenEndpoint = sessionStorage.getItem("oryma.local-oidc.token-endpoint");
  sessionStorage.removeItem(stateKey);
  sessionStorage.removeItem(verifierKey);
  sessionStorage.removeItem("oryma.local-oidc.token-endpoint");
  window.history.replaceState(null, "", redirectUri);

  if (oidcError) {
    throw new Error(`Connexion Keycloak refusée : ${oidcError}`);
  }
  if (!expectedState || returnedState !== expectedState || !verifier || !tokenEndpoint) {
    throw new Error("État OIDC absent ou invalide ; recommencez la connexion.");
  }

  const response = await fetch(tokenEndpoint, {
    method: "POST",
    credentials: "omit",
    cache: "no-store",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: clientId,
      code,
      redirect_uri: redirectUri,
      code_verifier: verifier,
    }),
  });
  const payload = await readJson(response);
  if (!response.ok || typeof payload.access_token !== "string") {
    throw new Error(payload.error_description || `Échange du code refusé (HTTP ${response.status}).`);
  }

  accessToken = payload.access_token;
  clearButton.disabled = false;
  enrollmentForm.hidden = false;
  showTokenClaims(accessToken);
}

loginButton.addEventListener("click", beginLogin);

clearButton.addEventListener("click", () => {
  accessToken = undefined;
  enrollmentForm.hidden = true;
  claimsSection.hidden = true;
  resultSection.hidden = true;
  clearButton.disabled = true;
  loginButton.disabled = false;
  setStatus("Jeton effacé de la mémoire de cet onglet.");
});

enrollmentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!accessToken) {
    setStatus("Reconnectez-vous avant d’appeler l’API.");
    return;
  }

  const values = new FormData(enrollmentForm);
  const functionName = String(values.get("fonction") || "").trim();
  const requestBody = {
    identifiant: String(values.get("identifiant")).trim(),
    nom_complet: String(values.get("nom_complet")).trim(),
    ministere_code: String(values.get("ministere_code")).trim(),
    fonction: functionName || null,
    role: String(values.get("role")),
  };
  const submitButton = enrollmentForm.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  setStatus("Appel authentifié de POST /api/v1/agents…");
  resultSection.hidden = true;

  try {
    const response = await fetch("/api/v1/agents", {
      method: "POST",
      credentials: "omit",
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(requestBody),
    });
    const payload = await readJson(response);
    document.querySelector("#result-output").textContent = JSON.stringify(payload, null, 2);
    resultSection.hidden = false;
    setStatus(`Réponse API : HTTP ${response.status}.`);
  } catch (error) {
    setStatus(error instanceof Error ? error.message : "Appel de l’API impossible.");
  } finally {
    submitButton.disabled = false;
  }
});

finishLogin().catch((error) => {
  loginButton.disabled = false;
  setStatus(error instanceof Error ? error.message : "Échec de la connexion OIDC.");
});
