/*
  filename: i18n.js
  description: Lightweight i18n for FE Copilot. Five languages (Elastic top markets), persisted in localStorage. UI chrome only; agent outputs are translated server-side via the language parameter.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/

const I18N_LOCALES = {
  en: { name: "English", flag: "🇺🇸", claudeName: "English" },
  es: { name: "Español", flag: "🇪🇸", claudeName: "Spanish" },
  ja: { name: "日本語", flag: "🇯🇵", claudeName: "Japanese" },
  de: { name: "Deutsch", flag: "🇩🇪", claudeName: "German" },
  fr: { name: "Français", flag: "🇫🇷", claudeName: "French" },
};

const I18N_STRINGS = {
  en: {
    "topbar.tag": "for Field Engineers",
    "topbar.connecting": "Connecting...",
    "topbar.connected": "Connected",
    "topbar.offline": "Backend offline",
    "topbar.dashboard": "Dashboard",

    "hero.title.1": "Three agents.",
    "hero.title.2": "One pre-meeting flow.",
    "hero.lede": "FE Copilot chains a Pre-Meeting Researcher, a Live Companion, and a Post-Meeting Action Engine on top of Claude. All sample data here is synthetic; no customer data was used.",
    "stats.accounts": "Accounts",
    "stats.upcoming": "Upcoming",
    "stats.past": "Past meetings",
    "stats.briefs": "Briefs generated",
    "stats.agents": "Chained agents",

    "tab.qr": "Pre-meeting research",
    "tab.tr": "Analyze transcript",

    "qr.title": "Quick research",
    "qr.subtitle": "Research any account in 10 seconds. Only what you type leaves the boundary.",
    "qr.field.company": "Company",
    "qr.field.industry": "Industry",
    "qr.field.size": "Size",
    "qr.field.stack": "Stack notes (optional)",
    "qr.field.notes": "Meeting context (optional)",
    "qr.placeholder.company": "e.g. Stripe, Mercado Libre, Banco Itau",
    "qr.placeholder.industry": "Fintech, Retail, Public sector...",
    "qr.placeholder.size": "Mid-market, Enterprise...",
    "qr.placeholder.stack": "Comma-separated. e.g. Splunk, AWS, ServiceNow",
    "qr.placeholder.notes": "What do you want to discuss? Recent signal? Blocker?",
    "qr.submit": "Generate brief",
    "qr.status": "Building dossier and calling Claude...",

    "tr.title": "Analyze transcript",
    "tr.subtitle": "Paste a Zoom .vtt, Gong export, or any 'Speaker: text' transcript. The Post-Meeting agent extracts action items, MEDDPICC signals, and competitor mentions.",
    "tr.field.company": "Company",
    "tr.field.title": "Meeting title",
    "tr.field.source": "Source",
    "tr.field.text": "Transcript",
    "tr.field.file": "Or upload a .vtt",
    "tr.placeholder.text": "Paste the transcript here, or drop a .vtt file below.",
    "tr.submit": "Analyze transcript",
    "tr.status": "Parsing transcript and calling Claude...",

    "section.upcoming": "Upcoming",
    "section.past": "Past",
    "section.meetings": "Meetings on file",
    "section.history": "History",
    "search.placeholder": "Filter by company, title, industry...",
    "btn.open": "Open",
    "btn.run.pre": "Run Pre-Meeting",
    "btn.run.post": "Run Post-Meeting",

    "footer.audit": "Audit log",
    "footer.audit.calls": "calls",
    "footer.audit.tokens": "in / {out} out tokens",
    "footer.audit.view": "view JSON",
    "footer.es": "Elasticsearch",
    "footer.kibana": "Kibana",
    "footer.kibana.setup": "create data views",
    "footer.es.reindex": "reindex disk → ES",
    "footer.es.reconnect": "reconnect",
    "footer.compliance": "Compliance",
    "footer.compliance.text": "Synthetic data · Append-only audit · Per-agent model override · See compliance.md",

    "meeting.brief": "Pre-Meeting Brief",
    "meeting.post": "Post-Meeting",
    "meeting.live": "Live Companion",
    "meeting.context": "Context",
    "meeting.btn.run.pre": "Run Pre-Meeting Agent",
    "meeting.btn.run.post": "Run Post-Meeting Agent",
    "meeting.btn.replay": "Replay transcript",
    "meeting.btn.download": "Download",
    "meeting.btn.print": "Print",

    "panel.brief": "Account brief",
    "panel.post": "Post-meeting output",
    "panel.live": "Live companion (Haiku)",
    "panel.context": "Context for this account",
    "panel.expand": "Expand all",
    "panel.collapse": "Collapse all",

    "lang.label": "Language",
  },

  es: {
    "topbar.tag": "para Field Engineers",
    "topbar.connecting": "Conectando...",
    "topbar.connected": "Conectado",
    "topbar.offline": "Backend desconectado",
    "topbar.dashboard": "Dashboard",

    "hero.title.1": "Tres agentes.",
    "hero.title.2": "Un solo flujo pre-meeting.",
    "hero.lede": "FE Copilot encadena un Pre-Meeting Researcher, un Live Companion y un Post-Meeting Action Engine sobre Claude. Toda la data aquí es sintética; no se usaron datos de clientes.",
    "stats.accounts": "Cuentas",
    "stats.upcoming": "Próximas",
    "stats.past": "Pasadas",
    "stats.briefs": "Briefs generados",
    "stats.agents": "Agentes encadenados",

    "tab.qr": "Investigación pre-meeting",
    "tab.tr": "Analizar transcripción",

    "qr.title": "Investigación rápida",
    "qr.subtitle": "Investigá cualquier cuenta en 10 segundos. Solo lo que tipeás sale del perímetro.",
    "qr.field.company": "Empresa",
    "qr.field.industry": "Industria",
    "qr.field.size": "Tamaño",
    "qr.field.stack": "Notas de stack (opcional)",
    "qr.field.notes": "Contexto de meeting (opcional)",
    "qr.placeholder.company": "Ej. Stripe, Mercado Libre, Banco Itau",
    "qr.placeholder.industry": "Fintech, Retail, Sector público...",
    "qr.placeholder.size": "Mid-market, Enterprise...",
    "qr.placeholder.stack": "Separado por comas. Ej. Splunk, AWS, ServiceNow",
    "qr.placeholder.notes": "¿Qué querés discutir? ¿Señal reciente? ¿Bloqueo?",
    "qr.submit": "Generar brief",
    "qr.status": "Armando dossier y llamando a Claude...",

    "tr.title": "Analizar transcripción",
    "tr.subtitle": "Pegá un .vtt de Zoom, export de Gong, o cualquier transcripción 'Hablante: texto'. El agente Post-Meeting extrae action items, señales MEDDPICC y menciones de competidores.",
    "tr.field.company": "Empresa",
    "tr.field.title": "Título de meeting",
    "tr.field.source": "Origen",
    "tr.field.text": "Transcripción",
    "tr.field.file": "O cargá un .vtt",
    "tr.placeholder.text": "Pegá la transcripción aquí o cargá un archivo .vtt debajo.",
    "tr.submit": "Analizar transcripción",
    "tr.status": "Parseando transcripción y llamando a Claude...",

    "section.upcoming": "Próximas",
    "section.past": "Pasadas",
    "section.meetings": "Meetings registradas",
    "section.history": "Historial",
    "search.placeholder": "Filtrar por empresa, título, industria...",
    "btn.open": "Abrir",
    "btn.run.pre": "Correr Pre-Meeting",
    "btn.run.post": "Correr Post-Meeting",

    "footer.audit": "Audit log",
    "footer.audit.calls": "llamadas",
    "footer.audit.tokens": "in / {out} out tokens",
    "footer.audit.view": "ver JSON",
    "footer.es": "Elasticsearch",
    "footer.kibana": "Kibana",
    "footer.kibana.setup": "crear data views",
    "footer.es.reindex": "reindexar disco → ES",
    "footer.es.reconnect": "reconectar",
    "footer.compliance": "Compliance",
    "footer.compliance.text": "Datos sintéticos · Audit append-only · Override de modelo por agente · Ver compliance.md",

    "meeting.brief": "Brief Pre-Meeting",
    "meeting.post": "Post-Meeting",
    "meeting.live": "Companion en vivo",
    "meeting.context": "Contexto",
    "meeting.btn.run.pre": "Correr agente Pre-Meeting",
    "meeting.btn.run.post": "Correr agente Post-Meeting",
    "meeting.btn.replay": "Reproducir transcripción",
    "meeting.btn.download": "Descargar",
    "meeting.btn.print": "Imprimir",

    "panel.brief": "Brief de cuenta",
    "panel.post": "Resultado Post-Meeting",
    "panel.live": "Companion en vivo (Haiku)",
    "panel.context": "Contexto de esta cuenta",
    "panel.expand": "Expandir todo",
    "panel.collapse": "Colapsar todo",

    "lang.label": "Idioma",
  },

  ja: {
    "topbar.tag": "Field Engineer向け",
    "topbar.connecting": "接続中...",
    "topbar.connected": "接続済み",
    "topbar.offline": "バックエンド接続不可",
    "topbar.dashboard": "ダッシュボード",

    "hero.title.1": "3つのエージェント。",
    "hero.title.2": "ひとつのプレミーティング・フロー。",
    "hero.lede": "FE Copilotは、Pre-Meeting Researcher、Live Companion、Post-Meeting Action EngineをClaudeの上で連携させます。ここで使用するデータはすべて合成データで、顧客データは使用していません。",
    "stats.accounts": "アカウント",
    "stats.upcoming": "今後",
    "stats.past": "過去",
    "stats.briefs": "生成済みブリーフ",
    "stats.agents": "連携エージェント",

    "tab.qr": "プレミーティング・リサーチ",
    "tab.tr": "トランスクリプト分析",

    "qr.title": "クイック・リサーチ",
    "qr.subtitle": "10秒であらゆる顧客アカウントを調査。入力した情報のみが外部に送信されます。",
    "qr.field.company": "会社名",
    "qr.field.industry": "業界",
    "qr.field.size": "規模",
    "qr.field.stack": "技術スタック (任意)",
    "qr.field.notes": "ミーティング文脈 (任意)",
    "qr.placeholder.company": "例: Stripe、Mercado Libre、Banco Itau",
    "qr.placeholder.industry": "フィンテック、小売、公共セクター...",
    "qr.placeholder.size": "中堅、エンタープライズ...",
    "qr.placeholder.stack": "カンマ区切り。例: Splunk, AWS, ServiceNow",
    "qr.placeholder.notes": "何を議論したいですか? 最近のシグナル? ブロッカー?",
    "qr.submit": "ブリーフを生成",
    "qr.status": "ドシエ作成中、Claude呼び出し中...",

    "tr.title": "トランスクリプト分析",
    "tr.subtitle": "Zoom .vtt、Gongエクスポート、または「話者: テキスト」形式のトランスクリプトを貼り付けてください。Post-Meetingエージェントがアクション項目、MEDDPICCシグナル、競合言及を抽出します。",
    "tr.field.company": "会社名",
    "tr.field.title": "ミーティングタイトル",
    "tr.field.source": "ソース",
    "tr.field.text": "トランスクリプト",
    "tr.field.file": "または .vtt をアップロード",
    "tr.placeholder.text": "トランスクリプトをここに貼り付けるか、下に .vtt ファイルをドロップしてください。",
    "tr.submit": "トランスクリプトを分析",
    "tr.status": "トランスクリプトを解析、Claude呼び出し中...",

    "section.upcoming": "今後",
    "section.past": "過去",
    "section.meetings": "登録ミーティング",
    "section.history": "履歴",
    "search.placeholder": "会社、タイトル、業界で絞り込み...",
    "btn.open": "開く",
    "btn.run.pre": "Pre-Meeting実行",
    "btn.run.post": "Post-Meeting実行",

    "footer.audit": "監査ログ",
    "footer.audit.calls": "コール",
    "footer.audit.tokens": "in / {out} out トークン",
    "footer.audit.view": "JSONを表示",
    "footer.es": "Elasticsearch",
    "footer.kibana": "Kibana",
    "footer.kibana.setup": "データビュー作成",
    "footer.es.reindex": "ディスク → ES再インデックス",
    "footer.es.reconnect": "再接続",
    "footer.compliance": "コンプライアンス",
    "footer.compliance.text": "合成データ · 追記専用監査 · エージェント別モデル指定 · compliance.md参照",

    "meeting.brief": "プレミーティング・ブリーフ",
    "meeting.post": "ポストミーティング",
    "meeting.live": "ライブ・コンパニオン",
    "meeting.context": "コンテキスト",
    "meeting.btn.run.pre": "Pre-Meetingエージェントを実行",
    "meeting.btn.run.post": "Post-Meetingエージェントを実行",
    "meeting.btn.replay": "トランスクリプトを再生",
    "meeting.btn.download": "ダウンロード",
    "meeting.btn.print": "印刷",

    "panel.brief": "アカウント・ブリーフ",
    "panel.post": "ポストミーティング結果",
    "panel.live": "ライブ・コンパニオン (Haiku)",
    "panel.context": "このアカウントのコンテキスト",
    "panel.expand": "すべて展開",
    "panel.collapse": "すべて折りたたみ",

    "lang.label": "言語",
  },

  de: {
    "topbar.tag": "für Field Engineers",
    "topbar.connecting": "Verbinde...",
    "topbar.connected": "Verbunden",
    "topbar.offline": "Backend offline",
    "topbar.dashboard": "Dashboard",

    "hero.title.1": "Drei Agenten.",
    "hero.title.2": "Ein Pre-Meeting-Flow.",
    "hero.lede": "FE Copilot verbindet einen Pre-Meeting-Researcher, einen Live-Companion und ein Post-Meeting-Action-Engine auf Claude. Alle Daten hier sind synthetisch; keine Kundendaten wurden verwendet.",
    "stats.accounts": "Accounts",
    "stats.upcoming": "Anstehend",
    "stats.past": "Vergangene",
    "stats.briefs": "Briefs erstellt",
    "stats.agents": "Verkettete Agenten",

    "tab.qr": "Pre-Meeting-Recherche",
    "tab.tr": "Transkript analysieren",

    "qr.title": "Schnellrecherche",
    "qr.subtitle": "Recherchiere jeden Account in 10 Sekunden. Nur was du eingibst verlässt den Perimeter.",
    "qr.field.company": "Unternehmen",
    "qr.field.industry": "Branche",
    "qr.field.size": "Größe",
    "qr.field.stack": "Stack-Notizen (optional)",
    "qr.field.notes": "Meeting-Kontext (optional)",
    "qr.placeholder.company": "z.B. Stripe, Mercado Libre, Banco Itau",
    "qr.placeholder.industry": "Fintech, Retail, öffentlicher Sektor...",
    "qr.placeholder.size": "Mid-market, Enterprise...",
    "qr.placeholder.stack": "Kommagetrennt. z.B. Splunk, AWS, ServiceNow",
    "qr.placeholder.notes": "Worüber willst du sprechen? Aktuelles Signal? Blocker?",
    "qr.submit": "Brief erstellen",
    "qr.status": "Erstelle Dossier und rufe Claude auf...",

    "tr.title": "Transkript analysieren",
    "tr.subtitle": "Füge ein Zoom .vtt, Gong-Export oder beliebiges 'Sprecher: Text'-Transkript ein. Der Post-Meeting-Agent extrahiert Action Items, MEDDPICC-Signale und Wettbewerber-Erwähnungen.",
    "tr.field.company": "Unternehmen",
    "tr.field.title": "Meeting-Titel",
    "tr.field.source": "Quelle",
    "tr.field.text": "Transkript",
    "tr.field.file": "Oder lade ein .vtt hoch",
    "tr.placeholder.text": "Transkript hier einfügen oder unten eine .vtt-Datei ablegen.",
    "tr.submit": "Transkript analysieren",
    "tr.status": "Parse Transkript und rufe Claude auf...",

    "section.upcoming": "Anstehend",
    "section.past": "Vergangene",
    "section.meetings": "Erfasste Meetings",
    "section.history": "Verlauf",
    "search.placeholder": "Nach Unternehmen, Titel, Branche filtern...",
    "btn.open": "Öffnen",
    "btn.run.pre": "Pre-Meeting starten",
    "btn.run.post": "Post-Meeting starten",

    "footer.audit": "Audit-Log",
    "footer.audit.calls": "Calls",
    "footer.audit.tokens": "in / {out} out Token",
    "footer.audit.view": "JSON anzeigen",
    "footer.es": "Elasticsearch",
    "footer.kibana": "Kibana",
    "footer.kibana.setup": "Data Views erstellen",
    "footer.es.reindex": "Disk → ES neu indizieren",
    "footer.es.reconnect": "neu verbinden",
    "footer.compliance": "Compliance",
    "footer.compliance.text": "Synthetische Daten · Append-only Audit · Modell-Override pro Agent · Siehe compliance.md",

    "meeting.brief": "Pre-Meeting-Brief",
    "meeting.post": "Post-Meeting",
    "meeting.live": "Live Companion",
    "meeting.context": "Kontext",
    "meeting.btn.run.pre": "Pre-Meeting-Agent starten",
    "meeting.btn.run.post": "Post-Meeting-Agent starten",
    "meeting.btn.replay": "Transkript abspielen",
    "meeting.btn.download": "Herunterladen",
    "meeting.btn.print": "Drucken",

    "panel.brief": "Account-Brief",
    "panel.post": "Post-Meeting-Ergebnis",
    "panel.live": "Live Companion (Haiku)",
    "panel.context": "Kontext für diesen Account",
    "panel.expand": "Alle ausklappen",
    "panel.collapse": "Alle einklappen",

    "lang.label": "Sprache",
  },

  fr: {
    "topbar.tag": "pour Field Engineers",
    "topbar.connecting": "Connexion...",
    "topbar.connected": "Connecté",
    "topbar.offline": "Backend hors ligne",
    "topbar.dashboard": "Tableau de bord",

    "hero.title.1": "Trois agents.",
    "hero.title.2": "Un seul flux pré-réunion.",
    "hero.lede": "FE Copilot enchaîne un Pre-Meeting Researcher, un Live Companion et un Post-Meeting Action Engine sur Claude. Toutes les données ici sont synthétiques; aucune donnée client n'est utilisée.",
    "stats.accounts": "Comptes",
    "stats.upcoming": "À venir",
    "stats.past": "Passées",
    "stats.briefs": "Briefs générés",
    "stats.agents": "Agents enchaînés",

    "tab.qr": "Recherche pré-réunion",
    "tab.tr": "Analyser un transcript",

    "qr.title": "Recherche rapide",
    "qr.subtitle": "Recherchez n'importe quel compte en 10 secondes. Seul ce que vous saisissez quitte le périmètre.",
    "qr.field.company": "Entreprise",
    "qr.field.industry": "Secteur",
    "qr.field.size": "Taille",
    "qr.field.stack": "Notes stack (optionnel)",
    "qr.field.notes": "Contexte de réunion (optionnel)",
    "qr.placeholder.company": "ex. Stripe, Mercado Libre, Banco Itau",
    "qr.placeholder.industry": "Fintech, Retail, Secteur public...",
    "qr.placeholder.size": "Mid-market, Entreprise...",
    "qr.placeholder.stack": "Séparé par virgules. ex. Splunk, AWS, ServiceNow",
    "qr.placeholder.notes": "De quoi voulez-vous discuter? Signal récent? Blocage?",
    "qr.submit": "Générer le brief",
    "qr.status": "Construction du dossier et appel à Claude...",

    "tr.title": "Analyser un transcript",
    "tr.subtitle": "Collez un .vtt Zoom, un export Gong, ou tout transcript 'Locuteur: texte'. L'agent Post-Meeting extrait les actions, signaux MEDDPICC et mentions de concurrents.",
    "tr.field.company": "Entreprise",
    "tr.field.title": "Titre de la réunion",
    "tr.field.source": "Source",
    "tr.field.text": "Transcript",
    "tr.field.file": "Ou téléversez un .vtt",
    "tr.placeholder.text": "Collez le transcript ici, ou déposez un fichier .vtt ci-dessous.",
    "tr.submit": "Analyser le transcript",
    "tr.status": "Analyse du transcript et appel à Claude...",

    "section.upcoming": "À venir",
    "section.past": "Passées",
    "section.meetings": "Réunions enregistrées",
    "section.history": "Historique",
    "search.placeholder": "Filtrer par entreprise, titre, secteur...",
    "btn.open": "Ouvrir",
    "btn.run.pre": "Lancer Pre-Meeting",
    "btn.run.post": "Lancer Post-Meeting",

    "footer.audit": "Journal d'audit",
    "footer.audit.calls": "appels",
    "footer.audit.tokens": "in / {out} out tokens",
    "footer.audit.view": "voir JSON",
    "footer.es": "Elasticsearch",
    "footer.kibana": "Kibana",
    "footer.kibana.setup": "créer les data views",
    "footer.es.reindex": "réindexer disque → ES",
    "footer.es.reconnect": "reconnecter",
    "footer.compliance": "Conformité",
    "footer.compliance.text": "Données synthétiques · Audit append-only · Override de modèle par agent · Voir compliance.md",

    "meeting.brief": "Brief pré-réunion",
    "meeting.post": "Post-réunion",
    "meeting.live": "Live Companion",
    "meeting.context": "Contexte",
    "meeting.btn.run.pre": "Lancer l'agent Pre-Meeting",
    "meeting.btn.run.post": "Lancer l'agent Post-Meeting",
    "meeting.btn.replay": "Rejouer le transcript",
    "meeting.btn.download": "Télécharger",
    "meeting.btn.print": "Imprimer",

    "panel.brief": "Brief du compte",
    "panel.post": "Résultat post-réunion",
    "panel.live": "Live companion (Haiku)",
    "panel.context": "Contexte du compte",
    "panel.expand": "Tout déplier",
    "panel.collapse": "Tout replier",

    "lang.label": "Langue",
  },
};

const I18N_LANG_KEY = "fec_lang";

function getLang() {
  const saved = localStorage.getItem(I18N_LANG_KEY);
  if (saved && I18N_STRINGS[saved]) return saved;
  // Best-effort browser detection (pick the first matching prefix).
  const nav = (navigator.language || "en").toLowerCase();
  for (const code of Object.keys(I18N_STRINGS)) {
    if (nav.startsWith(code)) return code;
  }
  return "en";
}

function setLang(code) {
  if (!I18N_STRINGS[code]) return;
  localStorage.setItem(I18N_LANG_KEY, code);
}

function t(key, fallback) {
  const lang = getLang();
  const dict = I18N_STRINGS[lang] || I18N_STRINGS.en;
  return dict[key] || I18N_STRINGS.en[key] || fallback || key;
}

// Walk the DOM and replace [data-i18n] textContent + [data-i18n-attr] attribute values.
function applyI18n(root) {
  root = root || document;
  root.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  root.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.placeholder = t(node.dataset.i18nPlaceholder);
  });
  root.querySelectorAll("[data-i18n-title]").forEach((node) => {
    node.title = t(node.dataset.i18nTitle);
  });
}

function renderLangPicker(host) {
  if (!host) return;
  host.innerHTML = "";
  const cur = getLang();
  const select = document.createElement("select");
  select.className = "lang-picker";
  select.title = t("lang.label");
  Object.entries(I18N_LOCALES).forEach(([code, info]) => {
    const opt = document.createElement("option");
    opt.value = code;
    opt.textContent = `${info.flag} ${info.name}`;
    if (code === cur) opt.selected = true;
    select.appendChild(opt);
  });
  select.addEventListener("change", () => {
    setLang(select.value);
    // Reload so all dynamic JS picks up new strings (simpler than re-rendering everything in place).
    location.reload();
  });
  host.appendChild(select);
}

function claudeLanguageName() {
  return (I18N_LOCALES[getLang()] || I18N_LOCALES.en).claudeName;
}
