// Show/hide conditional fields
const methodSelect = document.getElementById("analysis_method");
const freqParams = document.getElementById("frequency-params");
const detectionSelect = document.getElementById("detection_method");
const tksParams = document.getElementById("tks-params");
const rnrParams = document.getElementById("rnr-params");
const langSelect = document.getElementById("lang_select");
let currentLang = "en";

const I18N = {
  en: {
    langLabel: "Language",
    subtitle: "Clone Detection & Co-modification Analysis",
    sectionRepository: "Repository",
    labelRepoUrl: "Repository URL",
    sectionDetector: "Detector",
    labelDetectionMethod: "Clone Detection Method",
    optDetectionNormal: "Normal (CCFinderSW)",
    optDetectionTks: "TKS (Not implemented)",
    optDetectionRnr: "RNR (Not implemented)",
    labelTks: "TKS - Token Kind Size",
    labelRnr: "RNR - Ratio of Non-Repeated token kinds",
    badgeNotImplemented: "Not implemented",
    tooltipTks: "Token Kind Size",
    tooltipRnr: "Ratio of Non-Repeated token kinds",
    labelMinTokens: "Minimum Matching Tokens",
    tooltipMinTokens: "CCFinderSW minimum token threshold. Default is 50.",
    labelImportFilter: "Import line filtering",
    descImportFilter: "When enabled, import/include lines are commented out before clone detection.",
    labelForceRecompute: "Recompute after clearing previous results",
    descForceRecompute: "If filters or parameters changed, ignore previous outputs and rerun.",
    sectionParameters: "Parameters",
    labelComodMethod: "Co-modification Analysis Method",
    optComodSet: "Clone set",
    optComodPair: "Clone pair (Not implemented)",
    labelAnalysisMethod: "Commit Selection Method",
    tooltipAnalysisMethod: "How target commits are selected.",
    labelAnalysisFrequency: "Analysis Frequency (commit interval)",
    tooltipAnalysisFrequency: "Select every Nth commit from the latest commit.",
    labelSearchDepth: "Search Depth",
    tooltipSearchDepth: "Maximum commits to inspect while searching, -1 means unlimited.",
    labelMaxCommits: "Max Analysed Commits",
    tooltipMaxCommits: "Maximum commits to analyze, independent from SEARCH_DEPTH, -1 means unlimited.",
    runButton: "Run Analysis",
    executionLog: "Execution Log",
    statusRunning: "Running...",
    statusInputError: "Input Error",
    statusCompleted: "Completed",
    statusError: "Error occurred",
    statusConnectionError: "Connection Error",
    alertRequiredUrl: "Repository URL is required",
    errorRequiredUrl: "Repository URL is required",
    errorInvalidUrl: "Repository URL must be a GitHub repository URL",
    errorDetectionMethod: "Detection method must be one of normal,tks,rnr",
    errorDetectionNotImpl: "TKS and RNR are not implemented",
    errorTks: "TKS must be an integer greater than 0",
    errorRnr: "RNR must satisfy 0 < RNR <= 1",
    errorMinTokens: "Minimum matching tokens must be an integer greater than 0",
    errorImportFilter: "Import filtering must be true/false",
    errorComodMethod: "Co-modification method must be one of clone_set,clone_pair",
    errorComodNotImpl: "clone_pair is not implemented",
    errorAnalysisMethod: "Analysis method must be one of merge_commit,tag,frequency",
    errorAnalysisFrequency: "ANALYSIS_FREQUENCY must be an integer greater than 0",
    errorSearchDepth: "SEARCH_DEPTH must be an integer >= -1",
    errorMaxAnalyzed: "MAX_ANALYZED_COMMITS must be an integer >= -1",
    errorForceRecompute: "force_recompute must be true/false",
    errorApiValidation: "API validation error",
    errorWebSocket: "[error] WebSocket connection failed.",
    errorGeneric: "Error",
  },
  ja: {
    langLabel: "言語",
    subtitle: "クローン検出と同時修正分析",
    sectionRepository: "リポジトリ",
    labelRepoUrl: "リポジトリURL",
    sectionDetector: "クローン検出",
    labelDetectionMethod: "検出手法",
    optDetectionNormal: "通常 (CCFinderSW)",
    optDetectionTks: "TKS（未実装）",
    optDetectionRnr: "RNR（未実装）",
    labelTks: "TKS - トークンの種類数",
    labelRnr: "RNR - トークンの種類の非繰り返し度",
    badgeNotImplemented: "未実装",
    tooltipTks: "トークンの種類数（Token Kind Size）",
    tooltipRnr: "トークンの種類の非繰り返し度",
    labelMinTokens: "最小一致トークン数",
    tooltipMinTokens: "CCFinderSWの最小一致トークン数です。デフォルトは50です。",
    labelImportFilter: "import行のフィルタリング",
    descImportFilter: "有効にすると, クローン検出前に import/include 行をコメントアウトします。",
    labelForceRecompute: "既存結果を削除して再計算",
    descForceRecompute: "フィルタやパラメータを変更した場合に, 以前の結果を無視して再実行します。",
    sectionParameters: "同時修正",
    labelComodMethod: "判定手法",
    optComodSet: "クローンセット",
    optComodPair: "クローンペア（未実装）",
    labelAnalysisMethod: "分析コミット方式",
    tooltipAnalysisMethod: "分析対象とするコミットの選定基準です。",
    labelAnalysisFrequency: "ANALYSIS_FREQUENCY（コミット間隔）",
    tooltipAnalysisFrequency: "最新コミットから数えて N コミットごとに抽出します。",
    labelSearchDepth: "SEARCH_DEPTH",
    tooltipSearchDepth: "探索するコミット数の上限です, -1 で無制限。",
    labelMaxCommits: "MAX_ANALYZED_COMMITS",
    tooltipMaxCommits: "実際に分析するコミット数の上限です, -1 で無制限。",
    runButton: "分析を実行",
    executionLog: "実行ログ",
    statusRunning: "実行中...",
    statusInputError: "入力エラー",
    statusCompleted: "完了しました",
    statusError: "エラーが発生しました",
    statusConnectionError: "接続エラー",
    alertRequiredUrl: "Repository URLを入力してください。",
    errorRequiredUrl: "Repository URL は必須です",
    errorInvalidUrl: "Repository URL は GitHub リポジトリ URL を指定してください",
    errorDetectionMethod: "検出手法は normal,tks,rnr のいずれかです",
    errorDetectionNotImpl: "TKS と RNR は未実装です",
    errorTks: "TKS は 0 より大きい整数が必要です",
    errorRnr: "RNR は 0 より大きく 1 以下で指定してください",
    errorMinTokens: "最小一致トークン数は 0 より大きい整数が必要です",
    errorImportFilter: "import行フィルタリングは true/false で指定してください",
    errorComodMethod: "同時修正の判定手法は clone_set,clone_pair のいずれかです",
    errorComodNotImpl: "clone_pair は未実装です",
    errorAnalysisMethod: "分析コミット方式は merge_commit,tag,frequency のいずれかです",
    errorAnalysisFrequency: "ANALYSIS_FREQUENCY は 0 より大きい整数が必要です",
    errorSearchDepth: "SEARCH_DEPTH は -1 以上の整数が必要です",
    errorMaxAnalyzed: "MAX_ANALYZED_COMMITS は -1 以上の整数が必要です",
    errorForceRecompute: "force_recompute は true/false で指定してください",
    errorApiValidation: "API バリデーションエラー",
    errorWebSocket: "[error] WebSocket connection failed.",
    errorGeneric: "エラー",
  },
};

function t(key) {
  return I18N[currentLang][key] || key;
}

function setText(id, key) {
  const element = document.getElementById(id);
  if (element) {
    element.textContent = t(key);
  }
}

function applyLanguage(lang) {
  currentLang = lang;
  document.documentElement.lang = lang;
  setText("lang-label", "langLabel");
  setText("subtitle", "subtitle");
  setText("section-repository", "sectionRepository");
  setText("label-repo-url", "labelRepoUrl");
  setText("section-detector", "sectionDetector");
  setText("label-detection-method", "labelDetectionMethod");
  setText("opt-detection-normal", "optDetectionNormal");
  setText("opt-detection-tks", "optDetectionTks");
  setText("opt-detection-rnr", "optDetectionRnr");
  setText("label-tks", "labelTks");
  setText("label-rnr", "labelRnr");
  setText("badge-tks", "badgeNotImplemented");
  setText("badge-rnr", "badgeNotImplemented");
  setText("tooltip-tks", "tooltipTks");
  setText("tooltip-rnr", "tooltipRnr");
  setText("label-min-tokens", "labelMinTokens");
  setText("tooltip-min-tokens", "tooltipMinTokens");
  setText("label-import-filter", "labelImportFilter");
  setText("desc-import-filter", "descImportFilter");
  setText("label-force-recompute", "labelForceRecompute");
  setText("desc-force-recompute", "descForceRecompute");
  setText("section-parameters", "sectionParameters");
  setText("label-comod-method", "labelComodMethod");
  setText("opt-comod-set", "optComodSet");
  setText("opt-comod-pair", "optComodPair");
  setText("label-analysis-method", "labelAnalysisMethod");
  setText("tooltip-analysis-method", "tooltipAnalysisMethod");
  setText("label-analysis-frequency", "labelAnalysisFrequency");
  setText("tooltip-analysis-frequency", "tooltipAnalysisFrequency");
  setText("label-search-depth", "labelSearchDepth");
  setText("tooltip-search-depth", "tooltipSearchDepth");
  setText("label-max-commits", "labelMaxCommits");
  setText("tooltip-max-commits", "tooltipMaxCommits");
  setText("btn-run", "runButton");
  setText("execution-log-title", "executionLog");
  if (!document.getElementById("status-text").className) {
    setText("status-text", "statusRunning");
  }
}

langSelect.addEventListener("change", () => {
  applyLanguage(langSelect.value);
});

applyLanguage("en");

methodSelect.addEventListener("change", () => {
  freqParams.classList.toggle("visible", methodSelect.value === "frequency");
});
detectionSelect.addEventListener("change", () => {
  tksParams.classList.toggle("visible", detectionSelect.value === "tks");
  rnrParams.classList.toggle("visible", detectionSelect.value === "rnr");
});

// Log helpers
function classifyLine(text) {
  if (text.startsWith("[step")) return "log-step";
  if (text.startsWith("[error")) return "log-error";
  if (text.startsWith("[job")) return "log-job";
  return "log-normal";
}

function appendLog(text) {
  const box = document.getElementById("log-box");
  const span = document.createElement("span");
  span.className = classifyLine(text);
  span.textContent = text + "\n";
  box.appendChild(span);
  box.scrollTop = box.scrollHeight;
}

function isInteger(value) {
  return Number.isInteger(value);
}

function validateParams(params) {
  const errors = [];

  if (!params.url) {
    errors.push(t("errorRequiredUrl"));
  } else {
    const normalizedUrl =
      typeof params.url === "string"
        ? params.url.trim().replace(/\/+$/, "")
        : "";
    if (!/^https:\/\/github\.com\/[^/\s]+\/[^/\s]+$/.test(normalizedUrl)) {
      errors.push(t("errorInvalidUrl"));
    }
  }

  if (!["normal", "tks", "rnr"].includes(params.detection_method)) {
    errors.push(t("errorDetectionMethod"));
  }
  if (params.detection_method !== "normal") {
    errors.push(t("errorDetectionNotImpl"));
  }

  if (!isInteger(params.tks) || params.tks <= 0) {
    errors.push(t("errorTks"));
  }
  if (!(params.rnr > 0 && params.rnr <= 1)) {
    errors.push(t("errorRnr"));
  }

  if (!isInteger(params.min_tokens) || params.min_tokens <= 0) {
    errors.push(t("errorMinTokens"));
  }

  if (typeof params.import_filter !== "boolean") {
    errors.push(t("errorImportFilter"));
  }

  if (!["clone_set", "clone_pair"].includes(params.comod_method)) {
    errors.push(t("errorComodMethod"));
  }
  if (params.comod_method !== "clone_set") {
    errors.push(t("errorComodNotImpl"));
  }

  if (!["merge_commit", "tag", "frequency"].includes(params.analysis_method)) {
    errors.push(t("errorAnalysisMethod"));
  }

  if (!isInteger(params.analysis_frequency) || params.analysis_frequency <= 0) {
    errors.push(t("errorAnalysisFrequency"));
  }

  if (!isInteger(params.search_depth) || params.search_depth < -1) {
    errors.push(t("errorSearchDepth"));
  }

  if (!isInteger(params.max_analyzed_commits) || params.max_analyzed_commits < -1) {
    errors.push(t("errorMaxAnalyzed"));
  }

  if (typeof params.force_recompute !== "boolean") {
    errors.push(t("errorForceRecompute"));
  }

  return errors;
}

// Start analysis
async function startAnalysis() {
  const url = document.getElementById("url").value.trim();
  if (!url) { alert(t("alertRequiredUrl")); return; }

  const btn = document.getElementById("btn-run");
  btn.disabled = true;
  btn.textContent = t("statusRunning");

  const logPanel = document.getElementById("log-panel");
  const logBox = document.getElementById("log-box");
  logBox.innerHTML = "";
  logPanel.classList.add("visible");
  document.getElementById("spinner").style.display = "block";
  document.getElementById("status-text").textContent = t("statusRunning");
  document.getElementById("status-text").className = "";

  const params = {
    url,
    detection_method: document.getElementById("detection_method").value,
    tks: parseInt(document.getElementById("tks").value, 10),
    rnr: parseFloat(document.getElementById("rnr").value),
    min_tokens: parseInt(document.getElementById("min_tokens").value, 10),
    import_filter: document.getElementById("import_filter").checked,
    force_recompute: document.getElementById("force_recompute").checked,
    comod_method: document.getElementById("comod_method").value,
    analysis_method: document.getElementById("analysis_method").value,
    analysis_frequency: parseInt(document.getElementById("analysis_frequency").value, 10),
    search_depth: parseInt(document.getElementById("search_depth").value, 10),
    max_analyzed_commits: parseInt(document.getElementById("max_analyzed_commits").value, 10),
  };

  const errors = validateParams(params);
  if (errors.length > 0) {
    alert(errors.join("\n"));
    document.getElementById("spinner").style.display = "none";
    document.getElementById("status-text").textContent = t("statusInputError");
    document.getElementById("status-text").className = "status-error";
    btn.disabled = false;
    btn.textContent = t("runButton");
    return;
  }

  try {
    const resp = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    if (!resp.ok) {
      const errData = await resp.json();
      throw new Error(errData.detail || t("errorApiValidation"));
    }
    const data = await resp.json();
    const jobId = data.job_id;

    // Connect to WebSocket for live logs
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${location.host}/ws/logs/${jobId}`);

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "log") {
        appendLog(msg.line);
      } else if (msg.type === "status") {
        document.getElementById("spinner").style.display = "none";
        if (msg.status === "completed") {
          document.getElementById("status-text").textContent = t("statusCompleted");
          document.getElementById("status-text").className = "status-done";
        } else {
          document.getElementById("status-text").textContent = t("statusError");
          document.getElementById("status-text").className = "status-error";
        }
        btn.disabled = false;
        btn.textContent = t("runButton");
        ws.close();
      }
    };

    ws.onerror = () => {
      appendLog(t("errorWebSocket"));
      document.getElementById("spinner").style.display = "none";
      document.getElementById("status-text").textContent = t("statusConnectionError");
      document.getElementById("status-text").className = "status-error";
      btn.disabled = false;
      btn.textContent = t("runButton");
    };
  } catch (err) {
    appendLog("[error] " + err.message);
    document.getElementById("spinner").style.display = "none";
    document.getElementById("status-text").textContent = t("errorGeneric");
    document.getElementById("status-text").className = "status-error";
    btn.disabled = false;
    btn.textContent = t("runButton");
  }
}
