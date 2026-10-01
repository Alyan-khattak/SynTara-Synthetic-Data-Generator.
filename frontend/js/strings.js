// ═══════════════════════════════════════════════════════════════════
// strings.js — all user-visible text in one place
// ═══════════════════════════════════════════════════════════════════
// IMP: never scatter strings through index.html; change wording here only.
// Components reference STRINGS.xxx — never raw string literals.
// ==============================================================

export const STRINGS = {
  loading: {
    generate: "Generating data…",
    scores:   "Scoring…",
    config:   "Loading…",
  },
  error: {
    network:  "Network error. Check the server is running.",
    generate: "Generation failed.",
    noRuns:   "No runs yet.",
  },
  empty: {
    preview: "Run a query to see a preview.",
    runs:    "No saved runs.",
  },
  label: {
    module: {
      tabular:    "Tabular",
      relational: "Relational",
      documents:  "Documents",
      data_mode:  "Data Mode",
    },
  },
  btn: {
    generate: "Generate",
    save:     "Save Run",
    download: "Download CSV",
  },
  score: {
    validity: "Validity",
    fidelity: "Fidelity",
    utility:  "Utility",
    privacy:  "Privacy",
    overall:  "Overall",
  },
  status: {
    pending: "Pending",
    done:    "Done",
    failed:  "Failed",
  },
};
