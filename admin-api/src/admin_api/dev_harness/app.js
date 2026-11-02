const clientId = "console";
const issuer = `${window.location.origin}/auth/realms/oryma`;
const redirectUri = `${window.location.origin}/admin/`;
const stateKey = "oryma.local-oidc.state";
const verifierKey = "oryma.local-oidc.verifier";
const agentPageSize = 25;
const pageSize = 25;

let accessToken;
let isAdmin = false;
let agentCursor;
let auditCursor;
let roomCursor;
let selectedAgent;
let cachedLevels = [];
let currentAuditFilters = {};

const byId = (id) => document.getElementById(id);
const status = byId("status");
const loginButton = byId("login");
const logoutButton = byId("logout");
const navigation = byId("navigation");
const identity = byId("identity");
const enrollmentForm = byId("enrollment-form");
const revokeForm = byId("revoke-form");
const auditFilter = byId("audit-filter");
const roomForm = byId("room-form");

function setStatus(message) {
  status.textContent = message;
}

function setBusy(button, busy) {
  button.disabled = busy;
}

function base64Url(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

function randomBase64Url(byteLength) {
  return base64Url(crypto.getRandomValues(new Uint8Array(byteLength)));
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

function errorMessage(payload, statusCode) {
  const error = payload?.error;
  const message = error?.message || `La requête a échoué (HTTP ${statusCode}).`;
  return error?.code ? `${message} (${error.code})` : message;
}

async function apiRequest(path, options = {}) {
  if (!accessToken) throw new Error("Connectez-vous avant d’utiliser la console.");
  let response;
  try {
    response = await fetch(path, {
      ...options,
      credentials: "omit",
      cache: "no-store",
      headers: {
        ...options.headers,
        Authorization: `Bearer ${accessToken}`,
      },
    });
  } catch (error) {
    throw new Error(error instanceof Error ? `Connexion à l’API impossible : ${error.message}` : "Connexion à l’API impossible.");
  }
  const payload = await readJson(response);
  if (!response.ok) {
    const error = new Error(errorMessage(payload, response.status));
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return { response, payload };
}

function showView(viewName) {
  for (const section of document.querySelectorAll("[id^='view-']")) {
    section.hidden = section.id !== `view-${viewName}`;
  }
  for (const button of navigation.querySelectorAll("button[data-view]")) {
    button.setAttribute("aria-current", button.dataset.view === viewName ? "page" : "false");
  }
}

async function navigateTo(view) {
  if (!isAdmin && view !== "rooms") return;
  showView(view);
  if (view === "agents") await loadAgents();
  if (view === "audit") await loadAudit();
  if (view === "rooms") {
    if (!cachedLevels.length) await loadLevels();
    await loadRooms();
  }
}

async function loadDashboard() {
  const activityState = byId("dashboard-activity-state");
  const table = byId("dashboard-audit-table");
  activityState.textContent = "Chargement de l’activité récente…";
  table.replaceChildren();
  try {
    const { payload } = await apiRequest("/api/v1/audit?page_size=5");
    const items = payload.data?.items;
    if (!Array.isArray(items)) throw new Error("La réponse du journal d’audit est invalide.");
    if (!items.length) {
      activityState.textContent = "Aucun événement d’audit enregistré.";
      return;
    }
    for (const event of items) {
      const row = document.createElement("tr");
      textCell(row, formatDate(event.horodatage));
      textCell(row, event.action);
      textCell(row, event.acteur_id);
      textCell(row, event.cible_id);
      table.appendChild(row);
    }
    activityState.textContent = `${items.length} événement(s) récent(s).`;
  } catch (error) {
    activityState.textContent = `Activité indisponible : ${error.message}`;
  }
}

function textCell(row, value) {
  const cell = document.createElement("td");
  cell.textContent = value == null || value === "" ? "—" : String(value);
  row.appendChild(cell);
  return cell;
}

function makeBadge(label, className) {
  const badge = document.createElement("span");
  badge.className = `badge ${className}`;
  badge.textContent = label;
  return badge;
}

function clearTable(tableId) {
  byId(tableId).replaceChildren();
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("fr-FR");
}

function renderAgents(items) {
  const table = byId("agents-table");
  table.replaceChildren();
  for (const agent of items) {
    const row = document.createElement("tr");
    textCell(row, agent.nom_complet);
    textCell(row, agent.ministere_code);
    textCell(row, agent.fonction);
    textCell(row, agent.role);
    const statusCell = document.createElement("td");
    const revoked = agent.statut === "revoque";
    statusCell.appendChild(makeBadge(revoked ? "Révoqué" : "Actif", revoked ? "revoked" : "active"));
    row.appendChild(statusCell);
    const actions = document.createElement("td");
    const revokeButton = document.createElement("button");
    revokeButton.type = "button";
    revokeButton.className = "danger";
    revokeButton.textContent = "Révoquer";
    revokeButton.disabled = revoked;
    revokeButton.addEventListener("click", () => beginRevocation(agent));
    actions.appendChild(revokeButton);
    row.appendChild(actions);
    table.appendChild(row);
  }
}

function renderRevocation(payload, statusCode) {
  const data = statusCode >= 200 && statusCode < 300 ? payload?.data : payload?.error?.details;
  const steps = data?.etapes;
  const list = byId("revoke-steps");
  list.replaceChildren();
  if (Array.isArray(steps)) {
    for (const step of steps) {
      const item = document.createElement("li");
      item.textContent = `${step.ordre}. ${step.nom} : ${step.statut}${step.detail ? ` — ${step.detail}` : ""}`;
      if (step.statut === "echec") item.style.color = "#c62828";
      if (step.statut === "ignoree") item.style.color = "#8a5500";
      if (step.statut === "reussie") item.style.color = "#2e7d32";
      list.appendChild(item);
    }
  }
  byId("revoke-output").textContent = JSON.stringify(payload, null, 2);
  byId("retry-revocation").hidden = statusCode < 400 || !Array.isArray(steps);
}

async function revokeSelectedAgent() {
  const button = revokeForm.querySelector('button[type="submit"]');
  setBusy(button, true);
  setStatus("Révocation en cours : les six étapes sont exécutées côté serveur…");
  try {
    const { response, payload } = await apiRequest(
      `/api/v1/agents/${encodeURIComponent(selectedAgent.id)}/revoke`,
      { method: "POST" },
    );
    renderRevocation(payload, response.status);
    setStatus(`Révocation terminée : HTTP ${response.status}.`);
    await loadAgents();
  } catch (error) {
    const responsePayload = error.payload || { error: { message: error.message } };
    renderRevocation(responsePayload, error.status || 0);
    setStatus(error.message);
  } finally {
    setBusy(button, false);
  }
}

function beginRevocation(agent) {
  selectedAgent = agent;
  byId("revoke-warning").textContent = `Agent concerné : ${agent.nom_complet} (${agent.identifiant}).`;
  revokeForm.elements.confirmation.value = "";
  byId("revoke-steps").replaceChildren();
  byId("revoke-output").textContent = "";
  byId("retry-revocation").hidden = true;
  byId("revoke-panel").hidden = false;
  revokeForm.elements.confirmation.focus();
}

function renderAudit(items) {
  const table = byId("audit-table");
  table.replaceChildren();
  for (const event of items) {
    const row = document.createElement("tr");
    textCell(row, formatDate(event.horodatage));
    textCell(row, event.action);
    textCell(row, event.acteur_id);
    textCell(row, event.cible_id);
    textCell(row, event.details ? JSON.stringify(event.details) : "—");
    table.appendChild(row);
  }
}

function queryString(values) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== null && value !== "") query.set(key, value);
  }
  return query.toString();
}

async function loadAgents(cursor = undefined) {
  const values = {
    statut: byId("agent-status").value,
    ministere_code: byId("agent-ministry").value.trim(),
    page_size: agentPageSize,
    cursor,
  };
  setStatus("Chargement des agents…");
  try {
    const query = queryString(values);
    const { payload } = await apiRequest(`/api/v1/agents${query ? `?${query}` : ""}`);
    const data = payload.data;
    if (!Array.isArray(data?.items)) throw new Error("La réponse de la liste des agents est invalide.");
    renderAgents(cursor ? [...previousAgentItems, ...data.items] : data.items);
    previousAgentItems = cursor ? [...previousAgentItems, ...data.items] : data.items;
    agentCursor = data.next_cursor || undefined;
    byId("next-agents").hidden = !agentCursor;
    setStatus(`${previousAgentItems.length} agent(s) affiché(s).`);
  } catch (error) {
    setStatus(error.message);
  }
}

let previousAgentItems = [];

async function loadAudit(cursor = undefined) {
  const values = {
    ...currentAuditFilters,
    page_size: pageSize,
    cursor,
  };
  setStatus("Chargement du journal d’audit…");
  try {
    const query = queryString(values);
    const { payload } = await apiRequest(`/api/v1/audit${query ? `?${query}` : ""}`);
    const data = payload.data;
    if (!Array.isArray(data?.items)) throw new Error("La réponse du journal d’audit est invalide.");
    renderAudit(cursor ? [...previousAuditItems, ...data.items] : data.items);
    previousAuditItems = cursor ? [...previousAuditItems, ...data.items] : data.items;
    auditCursor = data.next_cursor || undefined;
    byId("next-audit").hidden = !auditCursor;
    setStatus(`${previousAuditItems.length} événement(s) affiché(s).`);
  } catch (error) {
    setStatus(error.message);
  }
}

let previousAuditItems = [];

function formatDuration(seconds) {
  const hours = Math.floor(seconds / 3600);
  const days = Math.floor(hours / 24);
  if (days) return `${days} jour(s)`;
  if (hours) return `${hours} heure(s)`;
  return `${Math.floor(seconds / 60)} minute(s)`;
}

function updateRoomPolicy() {
  const level = cachedLevels.find((item) => item.code === roomForm.elements.niveau.value);
  byId("room-policy").textContent = level
    ? `${level.libelle} — rétention côté serveur : ${formatDuration(level.duree_vie_secondes)}. Une copie déjà reçue peut rester sur un appareil.`
    : "Choisissez un niveau pour afficher sa durée de conservation.";
}

async function loadLevels() {
  const button = byId("load-levels");
  setBusy(button, true);
  setStatus("Chargement des niveaux de classification…");
  try {
    const { payload } = await apiRequest("/api/v1/levels");
    if (!Array.isArray(payload.data)) throw new Error("La réponse des niveaux est invalide.");
    cachedLevels = payload.data;
    const select = roomForm.elements.niveau;
    const options = [new Option("Sélectionnez un niveau…", "")];
    for (const level of cachedLevels) {
      if (typeof level.code !== "string" || typeof level.libelle !== "string") continue;
      options.push(new Option(`${level.libelle} (${level.code})`, level.code));
    }
    select.replaceChildren(...options);
    updateRoomPolicy();
    setStatus(`${cachedLevels.length} niveau(x) chargé(s).`);
  } catch (error) {
    setStatus(error.message);
  } finally {
    setBusy(button, false);
  }
}

function renderRooms(items) {
  const table = byId("rooms-table");
  table.replaceChildren();
  for (const room of items) {
    const row = document.createElement("tr");
    textCell(row, room.nom);
    const levelCell = document.createElement("td");
    const confidential = room.niveau === "CONFIDENTIEL";
    levelCell.appendChild(makeBadge(
      `${confidential ? "🔒" : "📢"} ${room.niveau}`,
      confidential ? "level-confidential" : "level-restricted",
    ));
    row.appendChild(levelCell);
    textCell(row, formatDuration(room.duree_vie_secondes));
    textCell(row, formatDate(room.cree_le));
    textCell(row, room.room_id);
    table.appendChild(row);
  }
}

async function loadRooms(cursor = undefined) {
  const button = byId("refresh-rooms");
  setBusy(button, true);
  setStatus("Chargement de vos salles…");
  try {
    const query = queryString({ page_size: pageSize, cursor });
    const { payload } = await apiRequest(`/api/v1/rooms${query ? `?${query}` : ""}`);
    const data = payload.data;
    if (!Array.isArray(data?.items)) throw new Error("La réponse des salles est invalide.");
    previousRoomItems = cursor ? [...previousRoomItems, ...data.items] : data.items;
    renderRooms(previousRoomItems);
    roomCursor = data.next_cursor || undefined;
    byId("next-rooms").hidden = !roomCursor;
    setStatus(`${previousRoomItems.length} salle(s) affichée(s).`);
  } catch (error) {
    setStatus(error.message);
  } finally {
    setBusy(button, false);
  }
}

let previousRoomItems = [];

function dateTimeFilter(value) {
  return value ? new Date(value).toISOString() : "";
}

async function beginLogin() {
  setStatus("Préparation de la connexion sécurisée…");
  setBusy(loginButton, true);
  try {
    const response = await fetch(`${issuer}/.well-known/openid-configuration`, {
      cache: "no-store",
      credentials: "omit",
    });
    if (!response.ok) throw new Error(`Découverte OIDC indisponible (HTTP ${response.status}).`);
    const discovery = await readJson(response);
    if (!discovery.authorization_endpoint || !discovery.token_endpoint) {
      throw new Error("La configuration OIDC ne contient pas les points d’accès attendus.");
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
    setBusy(loginButton, false);
    setStatus(error.message);
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

  if (oidcError) throw new Error(`Connexion Keycloak refusée : ${oidcError}`);
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
    throw new Error(payload.error_description || `Connexion refusée (HTTP ${response.status}).`);
  }

  accessToken = payload.access_token;
  const encoded = accessToken.split(".")[1];
  if (!encoded) throw new Error("Le jeton reçu n’est pas un JWT valide.");
  const normalized = encoded.replaceAll("-", "+").replaceAll("_", "/");
  const binary = atob(normalized + "=".repeat((4 - normalized.length % 4) % 4));
  const claims = JSON.parse(new TextDecoder().decode(
    Uint8Array.from(binary, (character) => character.charCodeAt(0)),
  ));
  const roles = claims.realm_access?.roles;
  const audience = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
  if (claims.azp !== clientId || !audience.includes("admin-api")) {
    accessToken = undefined;
    throw new Error("Le jeton console ne possède pas l’audience attendue.");
  }
  isAdmin = Array.isArray(roles) && roles.includes("admin");
  const isAgent = Array.isArray(roles) && roles.includes("agent");
  if (!isAdmin && !isAgent) {
    accessToken = undefined;
    throw new Error("Ce compte n’a pas de rôle Oryma autorisé.");
  }

  const name = claims.name || claims.preferred_username || "Compte connecté";
  identity.textContent = `${name} — ${isAdmin ? "Administrateur" : "Agent"}`;
  navigation.hidden = false;
  loginButton.hidden = true;
  logoutButton.disabled = false;
  for (const button of navigation.querySelectorAll("[data-view]")) {
    button.hidden = !isAdmin && button.dataset.view !== "rooms";
  }
  if (isAdmin) {
    byId("dashboard-greeting").textContent = `Bienvenue, ${name}`;
    await navigateTo("dashboard");
    await loadDashboard();
  } else {
    await navigateTo("rooms");
  }
  setStatus("Connexion réussie. Les règles d’accès restent appliquées par l’API.");
}

function clearSession() {
  accessToken = undefined;
  isAdmin = false;
  agentCursor = undefined;
  auditCursor = undefined;
  roomCursor = undefined;
  selectedAgent = undefined;
  previousAgentItems = [];
  previousAuditItems = [];
  previousRoomItems = [];
  cachedLevels = [];
  currentAuditFilters = {};
  identity.textContent = "";
  navigation.hidden = true;
  loginButton.hidden = false;
  logoutButton.disabled = true;
  for (const section of document.querySelectorAll("[id^='view-']")) section.hidden = true;
  byId("dashboard-greeting").textContent = "Tableau de bord administrateur";
  byId("dashboard-activity-state").textContent = "Connectez-vous pour consulter l’activité.";
  clearTable("dashboard-audit-table");
  byId("revoke-panel").hidden = true;
  byId("enrollment-result").hidden = true;
  byId("enrollment-output").textContent = "";
  byId("revoke-output").textContent = "";
  byId("room-summary").textContent = "";
  byId("room-error").textContent = "";
  byId("room-result").hidden = true;
  clearTable("agents-table");
  clearTable("audit-table");
  clearTable("rooms-table");
  setBusy(loginButton, false);
  setStatus("Session locale effacée. Le jeton en mémoire a été supprimé.");
}

loginButton.addEventListener("click", beginLogin);
logoutButton.addEventListener("click", clearSession);
navigation.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-view]");
  if (!button) return;
  await navigateTo(button.dataset.view);
});

byId("view-dashboard").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-dashboard-action]");
  if (!button || !isAdmin) return;
  const action = button.dataset.dashboardAction;
  await navigateTo(action === "enroll" ? "agents" : action);
  if (action === "enroll") {
    enrollmentForm.scrollIntoView({ behavior: "smooth", block: "start" });
    enrollmentForm.elements.identifiant.focus({ preventScroll: true });
  }
});

byId("refresh-agents").addEventListener("click", () => loadAgents());
byId("filter-agents").addEventListener("click", () => {
  previousAgentItems = [];
  loadAgents();
});
byId("next-agents").addEventListener("click", () => loadAgents(agentCursor));

enrollmentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = enrollmentForm.querySelector('button[type="submit"]');
  setBusy(button, true);
  byId("enrollment-result").hidden = true;
  setStatus("Enrôlement de l’agent…");
  const values = new FormData(enrollmentForm);
  const functionName = String(values.get("fonction") || "").trim();
  try {
    const { response, payload } = await apiRequest("/api/v1/agents", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        identifiant: String(values.get("identifiant")).trim(),
        nom_complet: String(values.get("nom_complet")).trim(),
        ministere_code: String(values.get("ministere_code")).trim(),
        fonction: functionName || null,
        role: String(values.get("role")),
      }),
    });
    byId("enrollment-output").textContent = JSON.stringify(payload.data, null, 2);
    byId("enrollment-result").hidden = false;
    enrollmentForm.reset();
    enrollmentForm.elements.ministere_code.value = "DEV-DEMO";
    setStatus(`Agent enrôlé : HTTP ${response.status}. Le mot de passe temporaire est visible ci-dessus.`);
    await loadAgents();
  } catch (error) {
    byId("enrollment-output").textContent = JSON.stringify(error.payload?.error || { message: error.message }, null, 2);
    byId("enrollment-result").hidden = false;
    setStatus(error.message);
  } finally {
    setBusy(button, false);
  }
});

revokeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedAgent || revokeForm.elements.confirmation.value.trim() !== selectedAgent.nom_complet) {
    setStatus("Le nom saisi ne correspond pas exactement à l’agent sélectionné.");
    return;
  }
  await revokeSelectedAgent();
});
byId("cancel-revoke").addEventListener("click", () => {
  selectedAgent = undefined;
  byId("revoke-panel").hidden = true;
});
byId("retry-revocation").addEventListener("click", revokeSelectedAgent);

auditFilter.addEventListener("submit", (event) => {
  event.preventDefault();
  const values = new FormData(auditFilter);
  currentAuditFilters = {
    action: String(values.get("action") || "").trim(),
    acteur_id: String(values.get("acteur_id") || "").trim(),
    depuis: dateTimeFilter(String(values.get("depuis") || "")),
    jusqu_a: dateTimeFilter(String(values.get("jusqu_a") || "")),
  };
  previousAuditItems = [];
  loadAudit();
});
byId("next-audit").addEventListener("click", () => loadAudit(auditCursor));

byId("load-levels").addEventListener("click", loadLevels);
roomForm.elements.niveau.addEventListener("change", updateRoomPolicy);
roomForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = roomForm.querySelector('button[type="submit"]');
  setBusy(button, true);
  byId("room-result").hidden = false;
  byId("room-summary").textContent = "";
  byId("room-error").textContent = "";
  const values = new FormData(roomForm);
  const memberText = String(values.get("membres") || "").trim();
  const members = memberText ? memberText.split(/[,\s]+/).filter(Boolean) : [];
  setStatus("Création de la salle chiffrée…");
  try {
    const { response, payload } = await apiRequest("/api/v1/rooms", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nom: String(values.get("nom") || "").trim(),
        niveau: String(values.get("niveau") || ""),
        membres: members,
      }),
    });
    const room = payload.data;
    byId("room-summary").textContent = [
      `room_id : ${room.room_id}`,
      `Nom : ${room.nom}`,
      `Niveau : ${room.niveau}`,
      `Durée de rétention : ${formatDuration(room.duree_vie_secondes)}`,
    ].join("\n");
    setStatus(`Salle créée : HTTP ${response.status}.`);
    roomForm.elements.nom.value = "";
    roomForm.elements.membres.value = "";
    await loadRooms();
  } catch (error) {
    byId("room-error").textContent = JSON.stringify(error.payload?.error || { message: error.message }, null, 2);
    setStatus(error.message);
  } finally {
    setBusy(button, false);
  }
});
byId("refresh-rooms").addEventListener("click", () => loadRooms());
byId("next-rooms").addEventListener("click", () => loadRooms(roomCursor));

finishLogin().catch((error) => {
  accessToken = undefined;
  setBusy(loginButton, false);
  setStatus(error instanceof Error ? error.message : "Échec de la connexion.");
});
