/**
 * Visualize画面用のi18n (英語/日本語切り替え)
 *
 * Dash の clientside_callback と連携して,
 * lang-store の値に応じて data-i18n 属性を持つ要素のテキストを差し替える.
 */
window.dash_clientside = window.dash_clientside || {};

const VIS_I18N = {
  en: {
    // Header
    headerTitle: "MSCCA Tools - Clone Explorer",
    // View buttons
    btnScatter: "Scatter Plot",
    btnExplorer: "Explorer",
    btnStats: "Statistics",
    // Sidebar
    sidebarExplorer: "EXPLORER",
    sidebarCloneOutline: "CLONE OUTLINE",
    editorPlaceholder: "Select a file to view",
    emptyState: "Select a file from the explorer to view its content.",
    // Filters
    filterComod: "Co-modification",
    filterScope: "Scope",
    filterCodeType: "Code Type",
    filterCloneId: "Clone ID",
    filterManyServices: "Multi-Service Clones",
    cloneIdPlaceholder: "Input Clone ID",
    manyServicesPlaceholder: "Select Clone ID (Multi-Service)",
    // Scatter details
    scatterClickHint: "Click a point on the graph to view clone details and code comparison here.",
    // Stats
    statsProjInfo: "Project Info",
    statsServiceInfo: "Service Info",
    statsCloneStats: "Clone Statistics",
    // Language selector
    langLabel: "Language",
    // Nav
    backToSettings: "Back to Settings",
    // 2-step project selection
    labelProject: "Project:",
    labelDataset: "Dataset:",
  },
  ja: {
    headerTitle: "MSCCA Tools - クローンエクスプローラ",
    btnScatter: "散布図",
    btnExplorer: "エクスプローラ",
    btnStats: "統計",
    sidebarExplorer: "エクスプローラ",
    sidebarCloneOutline: "クローンアウトライン",
    editorPlaceholder: "ファイルを選択してください",
    emptyState: "エクスプローラからファイルを選択すると, ここに内容が表示されます.",
    filterComod: "同時修正",
    filterScope: "スコープ",
    filterCodeType: "コードタイプ",
    filterCloneId: "クローンID",
    filterManyServices: "複数サービスクローン",
    cloneIdPlaceholder: "クローンIDを入力",
    manyServicesPlaceholder: "クローンIDを選択 (複数サービス)",
    scatterClickHint: "グラフ上の点をクリックすると, ここにクローンの詳細とコード比較が表示されます.",
    statsProjInfo: "プロジェクト情報",
    statsServiceInfo: "サービス情報",
    statsCloneStats: "クローン統計",
    langLabel: "言語",
    backToSettings: "設定画面に戻る",
    labelProject: "プロジェクト:",
    labelDataset: "データセット:",
  },
};

/**
 * data-i18n 属性を持つ全要素のテキストを切り替える.
 * placeholder が必要な input / dropdown も対応.
 */
function applyVisLanguage(lang) {
  const dict = VIS_I18N[lang] || VIS_I18N["en"];
  document.querySelectorAll("[data-i18n]").forEach(function (el) {
    var key = el.getAttribute("data-i18n");
    if (key && dict[key] !== undefined) {
      el.textContent = dict[key];
    }
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(function (el) {
    var key = el.getAttribute("data-i18n-placeholder");
    if (key && dict[key] !== undefined) {
      el.setAttribute("placeholder", dict[key]);
    }
  });
  document.documentElement.lang = lang;
}

// Dash clientside callback namespace
dash_clientside.i18n = {
  /**
   * clientside callback: lang-store が変わったら全テキストを差し替え.
   * Outputs は dummy の hidden div.
   */
  applyLang: function (lang) {
    if (lang) {
      applyVisLanguage(lang);
    }
    return "";
  },
};
