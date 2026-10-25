document.addEventListener("DOMContentLoaded", () => {
  const capabilitiesList = document.getElementById("capabilities-list");
  const capabilitySelect = document.getElementById("capability");
  const registerForm = document.getElementById("register-form");
  const targetEmail = document.getElementById("target-email");
  const registrationTitle = document.getElementById("registration-title");
  const registerSubmit = document.getElementById("register-submit");
  const messageDiv = document.getElementById("message");
  const authDialog = document.getElementById("auth-dialog");
  const loginForm = document.getElementById("login-form");
  const loginError = document.getElementById("login-error");
  const loginButton = document.getElementById("login-button");
  const logoutButton = document.getElementById("logout-button");
  const userIdentity = document.getElementById("user-identity");
  let currentUser = null;
  let csrfToken = "";

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[character]);
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      credentials: "same-origin",
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
        ...(options.headers || {}),
      },
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(result.detail || "The request could not be completed");
      error.status = response.status;
      throw error;
    }
    return result;
  }

  function showMessage(message, kind = "success") {
    messageDiv.textContent = message;
    messageDiv.className = kind;
    window.setTimeout(() => messageDiv.classList.add("hidden"), 5000);
  }

  function openLogin() {
    if (!authDialog.open) authDialog.showModal();
    document.getElementById("login-email").focus();
  }

  function setCurrentUser(user) {
    currentUser = user;
    const authenticated = Boolean(user);
    document.querySelectorAll(".auth-required").forEach((element) => {
      element.classList.toggle("hidden", !authenticated);
    });
    document.querySelectorAll(".lead-only").forEach((element) => {
      element.classList.toggle("hidden", user?.role !== "practice_lead");
    });
    loginButton.classList.toggle("hidden", authenticated);
    logoutButton.classList.toggle("hidden", !authenticated);
    userIdentity.classList.toggle("hidden", !authenticated);
    userIdentity.textContent = authenticated
      ? `${user.email} · ${user.role === "practice_lead" ? "Practice lead" : "Consultant"}`
      : "";
    targetEmail.required = user?.role === "practice_lead";
    registrationTitle.textContent = user?.role === "practice_lead"
      ? "Assign Expertise"
      : "Register Your Expertise";
    registerSubmit.textContent = user?.role === "practice_lead"
      ? "Register Consultant"
      : "Request Expertise";
  }

  function renderCapability(name, details) {
    const isLead = currentUser.role === "practice_lead" && details.can_manage;
    const activeConsultants = details.consultants || [];
    const pendingConsultants = details.pending_consultants || [];
    const trainingRequests = details.training_requests || [];
    const consultantsHTML = activeConsultants.length
      ? `<div class="consultants-section">
          <h5>Registered Consultants:</h5>
          <ul class="consultants-list">
            ${activeConsultants.map((email) => {
              const canRemove = isLead;
              const removeButton = canRemove
                ? `<button class="action-btn delete-btn" data-capability="${escapeHtml(name)}" data-email="${escapeHtml(email)}" type="button">${isLead ? "Remove" : "Withdraw"}</button>`
                : "";
              return `<li><span class="consultant-email">${escapeHtml(email)}</span>${removeButton}</li>`;
            }).join("")}
          </ul>
        </div>`
      : "<p><em>No consultants registered yet</em></p>";
    const pendingHTML = pendingConsultants.length
      ? `<div class="consultants-section pending-section">
          <h5>Pending Requests:</h5>
          <ul class="consultants-list">
            ${pendingConsultants.map((email) => {
              const action = isLead
                ? `<button class="action-btn approve-btn" data-capability="${escapeHtml(name)}" data-email="${escapeHtml(email)}" type="button">Approve</button>`
                : `<button class="action-btn delete-btn" data-capability="${escapeHtml(name)}" data-email="${escapeHtml(email)}" type="button">Withdraw</button>`;
              return `<li><span class="consultant-email">${escapeHtml(email)}</span>${action}</li>`;
            }).join("")}
          </ul>
        </div>`
      : "";
    const trainingHTML = trainingRequests.length
      ? `<div class="consultants-section pending-section">
          <h5>Training Requests:</h5>
          <ul class="training-list">
            ${trainingRequests.map((item) => {
              const review = isLead && item.status === "pending"
                ? `<button class="action-btn training-review-btn" data-capability="${escapeHtml(name)}" data-email="${escapeHtml(item.email)}" data-decision="approved" type="button">Approve</button>
                   <button class="action-btn delete-btn training-review-btn" data-capability="${escapeHtml(name)}" data-email="${escapeHtml(item.email)}" data-decision="declined" type="button">Decline</button>`
                : "";
              return `<li><div><strong>${escapeHtml(item.email)}</strong>
                <p>${escapeHtml(item.goal)}</p><small>Status: ${escapeHtml(item.status)}</small></div>${review}</li>`;
            }).join("")}
          </ul>
        </div>`
      : "";
    const trainingForm = !isLead
      ? `<form class="training-request-form" data-capability="${escapeHtml(name)}">
          <label>Request training
            <textarea name="goal" minlength="10" maxlength="1000" required placeholder="What capability would you like to develop, and why?"></textarea>
          </label>
          <button type="submit">Submit training request</button>
        </form>`
      : "";
    const consultantCount = activeConsultants.length;
    const capacity = Number.isFinite(details.capacity) ? details.capacity : 0;
    const managementHTML = isLead
      ? `<form class="requirements-form" data-capability="${escapeHtml(name)}">
          <h5>Practice lead controls</h5>
          <label>Weekly capacity (hours)
            <input name="capacity" type="number" min="0" max="168" value="${capacity}" required />
          </label>
          <label>Skill levels
            <input name="skill_levels" value="${escapeHtml((details.skill_levels || []).join(", "))}" required />
          </label>
          <label>Certifications
            <input name="certifications" value="${escapeHtml((details.certifications || []).join(", "))}" />
          </label>
          <button type="submit">Save requirements</button>
        </form>`
      : "";

    return `
      <article class="capability-card">
        <h4>${escapeHtml(name)}</h4>
        <p>${escapeHtml(details.description)}</p>
        <p><strong>Practice Area:</strong> ${escapeHtml(details.practice_area)}</p>
        <p><strong>Industry Verticals:</strong> ${escapeHtml((details.industry_verticals || []).join(", ") || "Not specified")}</p>
        <p><strong>Capacity:</strong> ${capacity} hours/week</p>
        <p><strong>Current Team:</strong> ${consultantCount} consultants</p>
        <div class="consultants-container">${consultantsHTML}${pendingHTML}${trainingHTML}</div>
        ${trainingForm}
        ${managementHTML}
      </article>`;
  }

  async function fetchCapabilities() {
    try {
      const capabilities = await api("/capabilities");
      capabilitiesList.innerHTML = "";
      while (capabilitySelect.options.length > 1) capabilitySelect.remove(1);

      Object.entries(capabilities).forEach(([name, details]) => {
        capabilitiesList.insertAdjacentHTML("beforeend", renderCapability(name, details));
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        capabilitySelect.appendChild(option);
      });

      document.querySelectorAll(".delete-btn").forEach((button) => {
        button.addEventListener("click", handleUnregister);
      });
      document.querySelectorAll(".approve-btn").forEach((button) => {
        button.addEventListener("click", handleApprove);
      });
      document.querySelectorAll(".requirements-form").forEach((form) => {
        form.addEventListener("submit", handleRequirementsUpdate);
      });
      document.querySelectorAll(".training-request-form").forEach((form) => {
        form.addEventListener("submit", handleTrainingRequest);
      });
      document.querySelectorAll(".training-review-btn").forEach((button) => {
        button.addEventListener("click", handleTrainingReview);
      });
      if (currentUser.role === "practice_lead") await fetchReport();
    } catch (error) {
      if (error.status === 401) {
        setCurrentUser(null);
        openLogin();
      } else {
        capabilitiesList.textContent = "Failed to load capabilities. Please try again.";
      }
    }
  }

  async function handleUnregister(event) {
    const button = event.currentTarget;
    const capability = button.dataset.capability;
    const email = button.dataset.email;
    try {
      const result = await api(
        `/capabilities/${encodeURIComponent(capability)}/unregister?email=${encodeURIComponent(email)}`,
        { method: "DELETE" },
      );
      showMessage(result.message);
      await fetchCapabilities();
    } catch (error) {
      showMessage(error.message, "error");
    }
  }

  async function handleApprove(event) {
    const button = event.currentTarget;
    const capability = button.dataset.capability;
    const email = button.dataset.email;
    try {
      const result = await api(
        `/capabilities/${encodeURIComponent(capability)}/approve?email=${encodeURIComponent(email)}`,
        { method: "POST" },
      );
      showMessage(result.message);
      await fetchCapabilities();
    } catch (error) {
      showMessage(error.message, "error");
    }
  }

  async function handleRequirementsUpdate(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const updates = {
      capacity: Number(values.get("capacity")),
      skill_levels: String(values.get("skill_levels"))
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean),
      certifications: String(values.get("certifications"))
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean),
    };
    try {
      await api(
        `/capabilities/${encodeURIComponent(form.dataset.capability)}/requirements`,
        { method: "PATCH", body: JSON.stringify(updates) },
      );
      showMessage("Capability requirements updated");
      await fetchCapabilities();
    } catch (error) {
      showMessage(error.message, "error");
    }
  }

  async function fetchReport() {
    try {
      const report = await api("/reports/capabilities");
      const byArea = Object.entries(report.by_practice_area)
        .map(([area, totals]) => `
          <tr>
            <th scope="row">${escapeHtml(area)}</th>
            <td>${totals.capabilities}</td>
            <td>${totals.registered_consultants}</td>
            <td>${totals.pending_requests}</td>
            <td>${totals.pending_training_requests}</td>
          </tr>`)
        .join("");
      document.getElementById("capability-report").innerHTML = `
        <p><strong>${report.capabilities}</strong> capabilities ·
          <strong>${report.registered_consultants}</strong> registrations ·
          <strong>${report.pending_requests}</strong> pending registrations ·
          <strong>${report.pending_training_requests}</strong> training requests to review</p>
        <div class="report-table-wrap">
          <table class="report-table">
            <thead><tr><th>Practice area</th><th>Capabilities</th><th>Registrations</th><th>Pending registrations</th><th>Training requests</th></tr></thead>
            <tbody>${byArea || "<tr><td colspan=\"5\">No capabilities</td></tr>"}</tbody>
          </table>
        </div>`;
    } catch (error) {
      document.getElementById("capability-report").textContent = error.message;
    }
  }

  async function handleTrainingRequest(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const goal = new FormData(form).get("goal");
    try {
      const result = await api(
        `/capabilities/${encodeURIComponent(form.dataset.capability)}/training-requests`,
        { method: "POST", body: JSON.stringify({ goal }) },
      );
      showMessage(result.message, "info");
      form.reset();
      await fetchCapabilities();
    } catch (error) {
      showMessage(error.message, "error");
    }
  }

  async function handleTrainingReview(event) {
    const button = event.currentTarget;
    const query = new URLSearchParams({
      email: button.dataset.email,
      decision: button.dataset.decision,
    });
    try {
      const result = await api(
        `/capabilities/${encodeURIComponent(button.dataset.capability)}/training-requests/review?${query}`,
        { method: "POST" },
      );
      showMessage(result.message);
      await fetchCapabilities();
    } catch (error) {
      showMessage(error.message, "error");
    }
  }

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    loginError.classList.add("hidden");
    const email = document.getElementById("login-email").value;
    const password = document.getElementById("login-password").value;
    try {
      const user = await api("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      csrfToken = user.csrf_token;
      setCurrentUser(user);
      loginForm.reset();
      authDialog.close();
      await fetchCapabilities();
    } catch (error) {
      loginError.textContent = error.message;
      loginError.classList.remove("hidden");
    }
  });

  loginButton.addEventListener("click", openLogin);
  logoutButton.addEventListener("click", async () => {
    try {
      await api("/auth/logout", { method: "POST" });
    } finally {
      csrfToken = "";
      setCurrentUser(null);
      capabilitiesList.innerHTML = "";
      openLogin();
    }
  });

  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const capability = capabilitySelect.value;
    const query = currentUser.role === "practice_lead"
      ? `?email=${encodeURIComponent(targetEmail.value.trim())}`
      : "";
    try {
      const result = await api(
        `/capabilities/${encodeURIComponent(capability)}/register${query}`,
        { method: "POST" },
      );
      showMessage(result.message, result.status === "pending" ? "info" : "success");
      registerForm.reset();
      await fetchCapabilities();
    } catch (error) {
      showMessage(error.message, "error");
    }
  });

  api("/auth/me")
    .then((user) => {
      csrfToken = user.csrf_token;
      setCurrentUser(user);
      return fetchCapabilities();
    })
    .catch(() => {
      setCurrentUser(null);
      openLogin();
    });
});
