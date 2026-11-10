/**
 * Cintamani Client API Wrapper.
 * Provides authenticated communication with /api/v1/* endpoints.
 */

const TOKEN_STORAGE_KEY = "cintamani_bearer_token";

class CintamaniAPI {
  constructor() {
    this.token = localStorage.getItem(TOKEN_STORAGE_KEY) || "";
  }

  setToken(newToken) {
    this.token = (newToken || "").trim();
    localStorage.setItem(TOKEN_STORAGE_KEY, this.token);
  }

  getToken() {
    return this.token;
  }

  hasToken() {
    return Boolean(this.token && this.token.length > 5);
  }

  async _request(path, options = {}) {
    const headers = {
      Accept: "application/json",
      ...(options.headers || {}),
    };

    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }

    if (options.body && typeof options.body === "object" && !(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(options.body);
    }

    const response = await fetch(path, { ...options, headers });

    if (response.status === 401) {
      throw new Error("UNAUTHORIZED: Token API tidak valid atau belum diisi.");
    }

    if (!response.ok) {
      let errDetail = `HTTP Error ${response.status}`;
      try {
        const errJson = await response.json();
        if (errJson.detail) errDetail = errJson.detail;
      } catch (e) {}
      throw new Error(errDetail);
    }

    return await response.json();
  }

  // 1. Health check
  async ping() {
    return await this._request("/api/v1/ping");
  }

  // 2. Micro Notes
  async getNotes(timeFilter = {}, limit = 100, offset = 0) {
    const params = new URLSearchParams({
      mode: timeFilter.mode || "all_time",
      limit: String(limit),
      offset: String(offset),
    });
    if (timeFilter.start_date) params.append("start_date", timeFilter.start_date);
    if (timeFilter.end_date) params.append("end_date", timeFilter.end_date);

    return await this._request(`/api/v1/notes?${params.toString()}`);
  }

  async createWebNote(content, pluginFlags = {}) {
    return await this._request("/api/v1/notes", {
      method: "POST",
      body: { content, plugin_flags: pluginFlags },
    });
  }

  // 3. Search (Keyword, Semantic, Hybrid)
  async searchNotes(query, searchType = "hybrid", timeFilter = {}, limit = 20) {
    const params = new URLSearchParams({
      q: query,
      search_type: searchType,
      mode: timeFilter.mode || "all_time",
      limit: String(limit),
    });
    if (timeFilter.start_date) params.append("start_date", timeFilter.start_date);
    if (timeFilter.end_date) params.append("end_date", timeFilter.end_date);

    return await this._request(`/api/v1/search?${params.toString()}`);
  }

  // 4. Dynamic Plugins
  async getActivePlugins(timeFilter = {}) {
    const params = new URLSearchParams({
      mode: timeFilter.mode || "all_time",
    });
    if (timeFilter.start_date) params.append("start_date", timeFilter.start_date);
    if (timeFilter.end_date) params.append("end_date", timeFilter.end_date);

    return await this._request(`/api/v1/active-plugins?${params.toString()}`);
  }

  // 5. Exploration & Jobs
  async triggerExplore(pluginName, timeFilter = {}, parameters = {}) {
    return await this._request("/api/v1/explore", {
      method: "POST",
      body: {
        plugin_name: pluginName,
        time_filter: {
          mode: timeFilter.mode || "all_time",
          start_date: timeFilter.start_date || null,
          end_date: timeFilter.end_date || null,
        },
        parameters,
      },
    });
  }

  async getJobStatus(jobId) {
    return await this._request(`/api/v1/jobs/${jobId}`);
  }

  // 6. Insights & Feedback
  async getInsights(pluginName = null, feedbackStatus = null, pinnedOnly = false, limit = 50) {
    const params = new URLSearchParams({ limit: String(limit) });
    if (pluginName) params.append("plugin_name", pluginName);
    if (feedbackStatus) params.append("feedback_status", feedbackStatus);
    if (pinnedOnly) params.append("pinned_only", "true");

    return await this._request(`/api/v1/insights?${params.toString()}`);
  }

  async updateFeedback(insightId, feedbackStatus = null, isPinned = null) {
    const body = {};
    if (feedbackStatus !== null) body.feedback_status = feedbackStatus;
    if (isPinned !== null) body.is_pinned = isPinned;

    return await this._request(`/api/v1/insights/${insightId}/feedback`, {
      method: "POST",
      body,
    });
  }

  // 7. Graph
  async getGraphData(timeFilter = {}) {
    const params = new URLSearchParams({
      mode: timeFilter.mode || "all_time",
    });
    if (timeFilter.start_date) params.append("start_date", timeFilter.start_date);
    if (timeFilter.end_date) params.append("end_date", timeFilter.end_date);

    return await this._request(`/api/v1/graph?${params.toString()}`);
  }

  // 8. Server Config
  async getServerConfig() {
    return await this._request("/api/v1/config");
  }

  async updateServerConfig(updates) {
    return await this._request("/api/v1/config", {
      method: "POST",
      body: updates,
    });
  }

  getExportUrl() {
    return `/api/v1/export`;
  }
}

window.api = new CintamaniAPI();
