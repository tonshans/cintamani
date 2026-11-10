/**
 * Cintamani Web Dashboard Vue 3 Application.
 * Connects the UI with /api/v1/* endpoints, Vis-Network Thought Constellation,
 * Async Job Polling, and Cognitive Neo-Brutalism Theme Engine.
 */

const { createApp, nextTick } = Vue;

createApp({
  data() {
    return {
      currentView: "stream", // "stream" | "insights" | "graph"
      currentTheme: "terminal",
      pingData: {
        status: "checking",
        server_time: "",
        ollama_reachable: false,
        llm_model: "qwen2.5:7b",
        llm_provider: "ollama",
      },
      timeFilter: {
        mode: "all_time",
        start_date: null,
        end_date: null,
      },
      notesList: [],
      totalNotes: 0,
      newNoteContent: "",
      searchQuery: "",
      searchType: "hybrid",
      searchResults: [],
      isSearching: false,
      activePlugins: [],
      insightsList: [],
      insightFilter: "all",
      isJobRunning: false,
      activeJobId: "",
      activeJobPlugin: "",
      jobPollingTimer: null,
      notificationMessage: "",
      notificationType: "info",
      showProvenanceModal: false,
      activeProvenanceInsight: {
        title: "",
        source_notes: [],
      },
      showSettingsModal: false,
      inputToken: "",
      serverConfig: {
        server_name: "Cintamani Home Brain",
        llm_provider: "ollama",
        ollama_base_url: "http://localhost:11434",
        llm_model: "qwen2.5:7b",
      },
      graphNetwork: null,
      selectedGraphItem: null,
    };
  },

  async mounted() {
    // 1. Initialize Theme
    if (window.CintamaniThemes) {
      this.currentTheme = window.CintamaniThemes.initTheme();
    }

    // 2. Setup Token (manual entry; token is printed by run.py / manage_token.py --show)
    this.inputToken = window.api.getToken();
    if (!window.api.hasToken()) {
      this.showSettingsModal = true;
    }

    // 3. Initial load
    await this.refreshAll();

    // Poll health status periodically
    setInterval(() => {
      this.checkHealth();
    }, 15000);
  },

  methods: {
    notify(msg, type = "info") {
      this.notificationMessage = msg;
      this.notificationType = type;
      setTimeout(() => {
        if (this.notificationMessage === msg) {
          this.notificationMessage = "";
        }
      }, 6000);
    },

    changeTheme() {
      if (window.CintamaniThemes) {
        window.CintamaniThemes.applyTheme(this.currentTheme);
      }
    },

    async checkHealth() {
      try {
        const res = await window.api.ping();
        this.pingData = res;
      } catch (err) {
        this.pingData.ollama_reachable = false;
      }
    },

    async refreshAll() {
      await this.checkHealth();
      await this.loadNotes();
      await this.loadActivePlugins();
      await this.loadInsights();
    },

    onTimeFilterChange() {
      this.loadNotes();
      this.loadActivePlugins();
      this.loadInsights();
      if (this.currentView === "graph") {
        this.loadGraphData();
      }
    },

    // -------------------------------------------------------------
    // Micro-Notes Operations
    // -------------------------------------------------------------
    async loadNotes() {
      try {
        const data = await window.api.getNotes(this.timeFilter, 100, 0);
        this.notesList = data.notes || [];
        this.totalNotes = data.total || 0;
      } catch (err) {
        if (err.message.includes("UNAUTHORIZED")) {
          this.showSettingsModal = true;
          this.notify("Masukkan API Token di menu Config untuk mulai sinkronisasi.", "error");
        }
      }
    },

    async submitWebNote() {
      if (!this.newNoteContent.trim()) return;

      try {
        const res = await window.api.createWebNote(this.newNoteContent.trim());
        this.newNoteContent = "";
        this.notify("Catatan mikro berhasil disimpan ke DuckDB!", "info");
        await this.loadNotes();
        await this.loadActivePlugins();
      } catch (err) {
        this.notify(`Gagal menyimpan catatan: ${err.message}`, "error");
      }
    },

    async performSearch() {
      if (!this.searchQuery.trim()) {
        this.resetSearch();
        return;
      }

      try {
        const res = await window.api.searchNotes(
          this.searchQuery.trim(),
          this.searchType,
          this.timeFilter,
          30
        );
        this.searchResults = res.results || [];
        this.isSearching = true;
      } catch (err) {
        this.notify(`Pencarian gagal: ${err.message}`, "error");
      }
    },

    resetSearch() {
      this.searchQuery = "";
      this.searchResults = [];
      this.isSearching = false;
    },

    // -------------------------------------------------------------
    // Dynamic Plugins & Exploration
    // -------------------------------------------------------------
    async loadActivePlugins() {
      try {
        const data = await window.api.getActivePlugins(this.timeFilter);
        this.activePlugins = data.plugins || [];
      } catch (err) {}
    },

    async triggerExplore(plugin) {
      if (!plugin.is_ready || this.isJobRunning) return;

      try {
        const res = await window.api.triggerExplore(
          plugin.plugin_name,
          this.timeFilter,
          {}
        );
        this.isJobRunning = true;
        this.activeJobId = res.job_id;
        this.activeJobPlugin = plugin.display_name;
        this.notify(`Eksplorasi '${plugin.display_name}' dijadwalkan...`, "info");

        // Start polling job status
        this.pollJob(res.job_id);
      } catch (err) {
        this.notify(`Gagal memulai eksplorasi: ${err.message}`, "error");
      }
    },

    pollJob(jobId) {
      if (this.jobPollingTimer) clearInterval(this.jobPollingTimer);

      this.jobPollingTimer = setInterval(async () => {
        try {
          const statusRes = await window.api.getJobStatus(jobId);
          if (statusRes.status === "completed") {
            clearInterval(this.jobPollingTimer);
            this.isJobRunning = false;
            this.notify(`Eksplorasi selesai! Membuka wawasan baru...`, "info");
            this.currentView = "insights";
            await this.loadInsights();
          } else if (statusRes.status === "failed") {
            clearInterval(this.jobPollingTimer);
            this.isJobRunning = false;
            this.notify(
              `Eksplorasi gagal: ${statusRes.error_message || "Kesalahan eksekusi"}`,
              "error"
            );
          }
        } catch (err) {
          clearInterval(this.jobPollingTimer);
          this.isJobRunning = false;
        }
      }, 2000);
    },

    // -------------------------------------------------------------
    // Insights & Feedback
    // -------------------------------------------------------------
    async loadInsights() {
      try {
        const statusFilter =
          this.insightFilter === "all" || this.insightFilter === "pinned"
            ? null
            : this.insightFilter;
        const pinnedOnly = this.insightFilter === "pinned";

        const res = await window.api.getInsights(null, statusFilter, pinnedOnly, 50);
        this.insightsList = res.insights || [];
      } catch (err) {}
    },

    async submitFeedback(insightId, feedbackStatus, isPinned) {
      try {
        await window.api.updateFeedback(insightId, feedbackStatus, isPinned);
        this.notify("Evaluasi berhasil disimpan ke Blackboard!", "info");
        await this.loadInsights();
      } catch (err) {
        this.notify(`Gagal memperbarui feedback: ${err.message}`, "error");
      }
    },

    openProvenance(insight) {
      this.activeProvenanceInsight = {
        title: insight.title,
        source_notes: insight.source_notes || [],
      };
      this.showProvenanceModal = true;
    },

    // -------------------------------------------------------------
    // Thought Constellation (Vis-Network Graph)
    // -------------------------------------------------------------
    async openGraphView() {
      this.currentView = "graph";
      await nextTick();
      this.loadGraphData();
    },

    async loadGraphData() {
      const container = document.getElementById("network-canvas");
      if (!container) return;

      try {
        const data = await window.api.getGraphData(this.timeFilter);

        // Styling based on active theme
        const isDark =
          this.currentTheme === "terminal" || this.currentTheme === "blueprint";
        const nodeColor = isDark ? "#4ADE80" : "#81A1C1";
        const nodeBorder = isDark ? "#F1F5F9" : "#111111";
        const nodeFont = isDark ? "#F1F5F9" : "#111111";
        const edgeColor = isDark ? "#94A3B8" : "#555555";

        const visNodes = (data.nodes || []).map((n) => ({
          id: n.id,
          label: n.label,
          title: this.escapeHtml(n.title),
          content: n.title,
          created_at: n.created_at,
          shape: "box",
          margin: 10,
          color: {
            background: isDark ? "#09090B" : "#FFFFFF",
            border: nodeBorder,
            highlight: {
              background: nodeColor,
              border: nodeBorder,
            },
          },
          borderWidth: 2,
          font: {
            color: nodeFont,
            face: "Plus Jakarta Sans",
            size: 12,
            bold: { mod: "bold" },
          },
        }));

        const visEdges = (data.edges || []).map((e) => ({
          id: e.id,
          from: e.from,
          to: e.to,
          label: e.label,
          title: this.escapeHtml(e.title),
          arrows: "to",
          color: { color: edgeColor, highlight: nodeColor },
          font: { color: nodeFont, size: 10, face: "JetBrains Mono" },
          width: Math.max(1, (e.weight || 0.5) * 3),
        }));

        const networkData = {
          nodes: new vis.DataSet(visNodes),
          edges: new vis.DataSet(visEdges),
        };

        const options = {
          physics: {
            barnesHut: {
              gravitationalConstant: -2500,
              centralGravity: 0.3,
              springLength: 120,
              springConstant: 0.04,
            },
            stabilization: { iterations: 100 },
          },
          interaction: {
            hover: true,
            tooltipDelay: 200,
          },
        };

        if (this.graphNetwork) {
          this.graphNetwork.destroy();
        }
        this.graphNetwork = new vis.Network(container, networkData, options);

        setTimeout(() => {
          if (this.graphNetwork) {
            this.graphNetwork.fit({ animation: { duration: 400, easingFunction: 'easeInOutQuad' } });
          }
        }, 200);

        // Click Handler for Inspector
        this.graphNetwork.on("click", (params) => {
          if (params.nodes.length > 0) {
            const nodeId = params.nodes[0];
            const nodeObj = visNodes.find((n) => n.id === nodeId);
            if (nodeObj) {
              this.selectedGraphItem = {
                type: "node",
                id: nodeObj.id,
                content: nodeObj.content,
                created_at: nodeObj.created_at,
              };
            }
          } else if (params.edges.length > 0) {
            const edgeId = params.edges[0];
            const edgeObj = visEdges.find((e) => e.id === edgeId);
            if (edgeObj) {
              this.selectedGraphItem = {
                type: "edge",
                id: edgeObj.id,
                title: edgeObj.title || edgeObj.label,
                content: `Relasi: ${edgeObj.label} (${edgeObj.from} ➔ ${edgeObj.to})`,
              };
            }
          } else {
            this.selectedGraphItem = null;
          }
        });
      } catch (err) {
        this.notify(`Gagal memuat graf: ${err.message}`, "error");
      }
    },

    // -------------------------------------------------------------
    // Backup & Settings
    // -------------------------------------------------------------
    async exportBrain() {
      try {
        const token = window.api.getToken();
        const res = await fetch("/api/v1/export", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error("Gagal mengunduh backup");

        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "cintamani_brain_export.json";
        document.body.appendChild(a);
        a.click();
        a.remove();
        this.notify("Dokumen backup 'cintamani_brain_export.json' berhasil diunduh!", "info");
      } catch (err) {
        this.notify(`Gagal export database: ${err.message}`, "error");
      }
    },

    async openSettings() {
      this.showSettingsModal = true;
      try {
        const cfg = await window.api.getServerConfig();
        this.serverConfig = {
          server_name: cfg.server_name,
          llm_provider: cfg.llm_provider,
          ollama_base_url: cfg.ollama_base_url,
          llm_model: cfg.llm_model,
        };
      } catch (err) {}
    },

    async saveSettings() {
      if (this.inputToken.trim()) {
        window.api.setToken(this.inputToken.trim());
      }

      try {
        await window.api.updateServerConfig({
          llm_provider: this.serverConfig.llm_provider,
          ollama_base_url: this.serverConfig.ollama_base_url,
          llm_model: this.serverConfig.llm_model,
        });
        this.showSettingsModal = false;
        this.notify("Pengaturan dan Token berhasil disimpan!", "info");
        await this.refreshAll();
      } catch (err) {
        this.showSettingsModal = false;
        this.notify("Token disimpan lokal. " + err.message, "info");
        await this.refreshAll();
      }
    },

    // Helpers
    renderMarkdown(text) {
      if (!text) return "";
      try {
        const html = marked.parse(text);
        if (window.DOMPurify) return window.DOMPurify.sanitize(html);
        return html.replace(/</g, "&lt;");
      } catch (e) {
        return String(text).replace(/</g, "&lt;");
      }
    },

    escapeHtml(value) {
      return String(value ?? "").replace(
        /[&<>"']/g,
        (c) =>
          ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;",
          })[c]
      );
    },

    formatTime(ts) {
      if (!ts) return "";
      try {
        const d = new Date(ts);
        return d.toLocaleString("id-ID", {
          year: "numeric",
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        });
      } catch (e) {
        return ts;
      }
    },
  },
}).mount("#app");
