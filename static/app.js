let pollingInterval = null;
let ultimoLogCount = 0;
let stockChartInstance = null;
let payoffChartInstance = null;
let estadoUltimoResultado = null;
let ativoSelecionado = "PETR4";
let todosDadosRanking = [];
let filtroStatusAtual = "todos";

// ========================================================
// CONTROLE DE PROGRESSO EM TEMPO REAL (0% - 100%)
// ========================================================
function atualizarProgresso(pct, texto) {
  const wrap = document.getElementById("progressWrapper");
  const fill = document.getElementById("progressFill");
  const text = document.getElementById("progressStepText");
  const pctEl = document.getElementById("progressPct");
  const spinner = document.getElementById("progressSpinner");

  if (wrap) wrap.style.display = "block";
  if (fill) fill.style.width = `${pct}%`;
  if (text) text.textContent = texto;
  if (pctEl) pctEl.textContent = `${pct}%`;

  if (pct >= 100) {
    if (spinner) spinner.textContent = "✅";
  } else if (pct > 0) {
    if (spinner) spinner.textContent = "⚡";
  }
}

// ========================================================
// CONTROLE DAS ABAS DO DASHBOARD FORMAL
// ========================================================
function trocarAba(aba, btnEl) {
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

  if (btnEl) {
    btnEl.classList.add("active");
  } else {
    const idBtn = aba === 'deliberacao' ? 'tabBtnDeliberacao' : (aba === 'graficos' ? 'tabBtnGraficos' : 'tabBtnRanking');
    const b = document.getElementById(idBtn);
    if (b) b.classList.add("active");
  }

  const idContent = aba === 'deliberacao' ? 'tabContentDeliberacao' : (aba === 'graficos' ? 'tabContentGraficos' : 'tabContentRanking');
  const target = document.getElementById(idContent);
  if (target) target.classList.add("active");

  if (aba === 'graficos') {
    setTimeout(() => {
      if (stockChartInstance) stockChartInstance.resize();
      if (payoffChartInstance) payoffChartInstance.resize();
    }, 50);
  }
}

// ========================================================
// SELEÇÃO INTERATIVA DE ATIVOS & CONSULTA DINÂMICA
// ========================================================
async function selecionarAtivo(ticker, btnEl) {
  ticker = ticker.toUpperCase().trim();
  ativoSelecionado = ticker;

  document.querySelectorAll(".quick-asset-btn").forEach(b => b.classList.remove("active"));
  if (btnEl) {
    btnEl.classList.add("active");
  } else {
    const b = document.getElementById(`btnQuick${ticker}`);
    if (b) b.classList.add("active");
  }

  const pill = document.getElementById("tabAtivoPill");
  if (pill) pill.textContent = ticker;

  try {
    const res = await fetch(`/api/ativo/${ticker}`);
    const data = await res.json();
    if (data.status === "sucesso") {
      renderizarGraficos(data);
    }
  } catch (err) {
    console.error(`Erro ao consultar dados de ${ticker}:`, err);
  }
}

function buscarAtivoManual(e) {
  if (e) e.preventDefault();
  const input = document.getElementById("manualTickerInput");
  const val = (input?.value || "").toUpperCase().trim();
  if (val) {
    selecionarAtivo(val, null);
  }
}

function verGraficoDoRanking(ticker) {
  trocarAba('graficos');
  selecionarAtivo(ticker, null);
}

// ========================================================
// EXECUÇÃO E STATUS DA ESTEIRA
// ========================================================
let progressoVisualAtual = 5;
let timerAnimacaoProgresso = null;

function iniciarAnimacaoSuaveProgresso(alvoMaximo) {
  if (timerAnimacaoProgresso) clearInterval(timerAnimacaoProgresso);
  timerAnimacaoProgresso = setInterval(() => {
    if (progressoVisualAtual < alvoMaximo) {
      progressoVisualAtual = Math.min(alvoMaximo, progressoVisualAtual + 0.35);
      const fill = document.getElementById("progressFill");
      const pctEl = document.getElementById("progressPct");
      if (fill) fill.style.width = `${Math.round(progressoVisualAtual)}%`;
      if (pctEl) pctEl.textContent = `${Math.round(progressoVisualAtual)}%`;
    }
  }, 1000);
}

async function iniciarAnalise() {
  const btn = document.getElementById("btnIniciar");
  btn.disabled = true;
  btn.innerHTML = `<span class="btn-icon">⏳</span><span class="btn-text">Executando Esteira...</span>`;

  try {
    const res = await fetch("/api/iniciar", { method: "POST" });
    const data = await res.json();
    
    atualizarPill("running", "Em Execução...");
    progressoVisualAtual = 8;
    atualizarProgresso(8, "Iniciando esteira multiagente e conectando a APIs...");
    iniciarAnimacaoSuaveProgresso(14);
    resetarAgentes();
    trocarAba('deliberacao');

    if (data.status === "concluido") {
      await verificarStatus();
      return;
    }

    if (!pollingInterval) {
      pollingInterval = setInterval(verificarStatus, 1500);
    }
  } catch (err) {
    alert("Erro ao conectar com o servidor: " + err.message);
    btn.disabled = false;
    btn.innerHTML = `<span class="btn-icon">🚀</span><span class="btn-text">Disparar Análise da Mesa</span>`;
  }
}

let isDemoAmbiente = false;

async function verificarStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();

    if (typeof data.is_demo !== "undefined") {
      isDemoAmbiente = Boolean(data.is_demo);
      const banner = document.getElementById("demoBanner");
      if (banner) {
        banner.style.display = isDemoAmbiente ? "flex" : "none";
      }
    }

    atualizarLogs(data.logs || []);

    if (data.status === "executando") {
      atualizarPill("running", "Processando Pipeline...");
      animarProgressoAgentes(data);
    } else if (data.status === "concluido") {
      if (timerAnimacaoProgresso) clearInterval(timerAnimacaoProgresso);
      atualizarPill("ready", "Análise Concluída");
      marcarTodosConcluidos();
      estadoUltimoResultado = data.resultado;
      exibirResultado(data.resultado);
      renderizarGraficos(data.graficos);
      carregarRanking();
      resetarBotao();
      clearInterval(pollingInterval);
      pollingInterval = null;
      progressoVisualAtual = 100;
      atualizarProgresso(100, isDemoAmbiente ? "Fluxo Demonstrativo Concluído! Relatório e deliberação disponíveis." : "Esteira Concluída! Relatório oficial e deliberação disponíveis.");

      const isAprov = data.resultado && data.resultado.status_decisao && data.resultado.status_decisao.includes("APROVAD");
      const tabPill = document.getElementById("tabStatusPill");
      if (tabPill) tabPill.textContent = isAprov ? "APROVADO" : "VETADO (CAIXA)";
    } else if (data.status === "erro") {
      if (timerAnimacaoProgresso) clearInterval(timerAnimacaoProgresso);
      atualizarPill("error", "Erro na Execução");
      const detalheErro = data.erro ? `Falha: ${data.erro}` : "Ocorreu uma falha na execução da esteira.";
      atualizarProgresso(0, detalheErro);
      resetarBotao();
      clearInterval(pollingInterval);
      pollingInterval = null;
    }
  } catch (err) {
    console.error("Falha ao consultar status:", err);
  }
}

function atualizarPill(tipo, texto) {
  const pill = document.getElementById("statusPill");
  const label = document.getElementById("statusLabel");
  pill.className = `status-pill ${tipo}`;
  label.textContent = texto;
}

function resetarBotao() {
  const btn = document.getElementById("btnIniciar");
  if (!btn) return;
  btn.disabled = false;
  if (isDemoAmbiente) {
    btn.innerHTML = `<span class="btn-icon">👁️</span><span class="btn-text">Visualizar Demonstração</span>`;
  } else {
    btn.innerHTML = `<span class="btn-icon">🚀</span><span class="btn-text">Disparar Análise da Mesa</span>`;
  }
}

function resetarAgentes() {
  for (let i = 1; i <= 6; i++) {
    const card = document.getElementById(`agent-${i}`);
    const badge = document.getElementById(`badge-${i}`);
    if (card && badge) {
      card.className = "agent-card";
      badge.textContent = "Pendente";
    }
  }
}

function animarProgressoAgentes(data) {
  const etapa = data.etapa_atual || 1;
  const progressoBase = data.progresso_pct || 15;
  const logs = data.logs || [];

  let ativo = etapa;
  let mensagem = "Fase 1/6: Analista Macro varrendo notícias, Selic, Fed e pré-selecionando ativos...";
  let teto = 32;

  if (ativo === 1) {
    mensagem = "Fase 1/6: Analista Macro varrendo notícias, Selic, Fed e pré-selecionando ativos...";
    teto = 32;
  } else if (ativo === 2) {
    mensagem = "Fase 2/6: Fundamentalista auditando múltiplos dos 100 ativos do IBrX-100 via BRAPI...";
    teto = 52;
  } else if (ativo === 3) {
    mensagem = "Fase 3/6: Analista Técnico CNPI-T calculando médias (SMA20/50), suportes, RSI-14 e checklist Dow...";
    teto = 72;
  } else if (ativo === 4) {
    mensagem = "Fase 4/6: Estrategista estruturando opções e precificando Gregas Black-Scholes...";
    teto = 88;
  } else if (ativo === 5) {
    mensagem = "Fase 5/6: Coordenador de Risco aplicando sarrafo de R/R >= 1.50:1 e governança...";
    teto = 96;
  } else if (ativo === 6) {
    mensagem = "Fase 6/6: Research Publisher gerando PDF executivo oficial (Resolução CVM nº 20)...";
    teto = 99;
  }

  // Se o backend avançou de fase, eleva o progresso visual imediatamente
  if (progressoVisualAtual < progressoBase) {
    progressoVisualAtual = progressoBase;
  }

  atualizarProgresso(Math.round(progressoVisualAtual), mensagem);
  iniciarAnimacaoSuaveProgresso(teto);

  for (let i = 1; i <= 6; i++) {
    const card = document.getElementById(`agent-${i}`);
    const badge = document.getElementById(`badge-${i}`);
    if (!card || !badge) continue;

    if (i < ativo) {
      card.className = "agent-card completed";
      badge.textContent = "Concluído";
    } else if (i === ativo) {
      card.className = "agent-card running";
      badge.textContent = "Executando";
    } else {
      card.className = "agent-card";
      badge.textContent = "Aguardando";
    }
  }
}

function marcarTodosConcluidos() {
  for (let i = 1; i <= 6; i++) {
    const card = document.getElementById(`agent-${i}`);
    const badge = document.getElementById(`badge-${i}`);
    if (card && badge) {
      card.className = "agent-card completed";
      badge.textContent = "Concluído";
    }
  }
}

function exibirResultado(res) {
  if (!res) return;

  const section = document.getElementById("resultSection");
  section.style.display = "block";

  const isAprovado = res.status_decisao && res.status_decisao.includes("APROVAD");
  const badgeStatus = document.getElementById("decisionStatusBadge");
  badgeStatus.textContent = res.status_decisao || (isAprovado ? "APROVADO" : "REPROVADO_TOTAL");
  badgeStatus.className = `status-badge ${isAprovado ? 'approved' : 'rejected'}`;

  const riskContainer = document.getElementById("riskBlockContainer");
  if (riskContainer) {
    riskContainer.className = `info-block risk-block ${isAprovado ? '' : 'veto'}`;
  }

  document.getElementById("relatorioTitulo").textContent = res.titulo || "Deliberação da Mesa de Operações";
  document.getElementById("relatorioData").textContent = `Emitido em: ${res.data || new Date().toLocaleString()}`;
  document.getElementById("relatorioTese").textContent = res.resumo_executivo || "N/A";
  document.getElementById("relatorioRisco").textContent = res.gestao_risco || "N/A";
  document.getElementById("relatorioCvm").textContent = res.disclaimer_cvm || "Em conformidade com a Resolução CVM 20/2021.";

  // Preenche a tabela de parâmetros operacionais
  const tbody = document.getElementById("paramsTableBody");
  tbody.innerHTML = "";

  const parametros = res.parametros || [];
  if (Array.isArray(parametros)) {
    parametros.forEach(item => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${item.parametro || item}</td>
        <td><strong>${item.valor || ""}</strong></td>
      `;
      tbody.appendChild(tr);
    });
  }

  // Preenche Gregas se houver
  const gregas = res.gregas;
  const gregasBlock = document.getElementById("gregasBlock");
  if (gregas && gregas.delta !== undefined && gregas.delta !== 0) {
    gregasBlock.style.display = "block";
    document.getElementById("gregaDelta").textContent = gregas.delta;
    document.getElementById("gregaGamma").textContent = gregas.gamma;
    document.getElementById("gregaTheta").textContent = gregas.theta;
    document.getElementById("gregaVega").textContent = gregas.vega;
  } else {
    gregasBlock.style.display = "none";
  }
}

function renderizarGraficos(graficos) {
  if (!graficos) return;

  const chartsSection = document.getElementById("chartsSection");
  if (chartsSection) chartsSection.style.display = "block";

  const ativo = graficos.ativo || "PETR4";
  const titleEl = document.getElementById("chartStockTitle");
  if (titleEl) {
    titleEl.innerHTML = `${ativo} &middot; Fechamentos & Níveis Técnicos (30D)`;
  }

  const tabAtivoPill = document.getElementById("tabAtivoPill");
  if (tabAtivoPill) tabAtivoPill.textContent = ativo;

  // Atualiza banner explicativo da Curva de Payoff
  const banner = document.getElementById("payoffAlertBanner");
  const bannerTitle = document.getElementById("payoffBannerTitle");
  const bannerDesc = document.getElementById("payoffBannerDesc");
  const chartPayoffTag = document.getElementById("chartPayoffTag");

  const isAprovado = estadoUltimoResultado && 
                     estadoUltimoResultado.status_decisao && 
                     estadoUltimoResultado.status_decisao.includes("APROVAD") && 
                     (ativo === estadoUltimoResultado.ativo);

  if (banner && bannerTitle && bannerDesc) {
    if (isAprovado) {
      banner.className = "payoff-status-banner aprovado";
      bannerTitle.textContent = "ESTRUTURA HOMOLOGADA PELA MESA DE OPERAÇÕES";
      bannerDesc.innerHTML = `A operação em <strong>${ativo}</strong> foi formalmente homologada pelo Comitê de Risco com relação Risco/Retorno &ge; 1.50:1. Alvos e stops validados.`;
      if (chartPayoffTag) chartPayoffTag.textContent = "DERIVATIVOS · ESTRATÉGIA HOMOLOGADA";
    } else {
      banner.className = "payoff-status-banner vetado";
      bannerTitle.textContent = `SIMULAÇÃO DE ESTRUTURA · OPERAÇÃO VETADA PELO RISCO (MANTER EM CAIXA)`;
      bannerDesc.innerHTML = `Aviso: A estrutura de opções para <strong>${ativo}</strong> foi rejeitada por apresentar Risco/Retorno inferior ao sarrafo mínimo de 1.50:1. A curva de payoff acima é exibida <strong>estritamente para fins de auditoria e estudo de sensibilidade</strong>. A diretriz oficial da Mesa é: <strong>MANTER 100% EM CAIXA / CDI</strong>.`;
      if (chartPayoffTag) chartPayoffTag.textContent = "DERIVATIVOS · SIMULAÇÃO NÃO AUTORIZADA";
    }
  }

  // 1. Gráfico de Fechamentos & Indicadores Técnicos
  const candles = (graficos.candles && graficos.candles.length > 0) ? graficos.candles : [];
  let labels = [];
  let closes = [];

  if (candles.length > 0) {
    labels = candles.map((c, idx) => {
      if (c.date_str) return c.date_str;
      if (typeof c.date === "number") {
        const ms = c.date > 1e11 ? c.date : c.date * 1000;
        const d = new Date(ms);
        return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`;
      }
      if (typeof c.date === "string") {
        return c.date.includes("T") ? c.date.split("T")[0].substring(5) : c.date;
      }
      return `D-${candles.length - idx}`;
    });
    closes = candles.map(c => c.close || c.fechamento || 0);
  } else {
    // Fallback prudencial para garantir que o canvas nunca fique em branco
    const base = graficos.preco_atual || 48.09;
    labels = ["26/08", "29/08", "02/09", "05/09", "09/09", "12/09", "16/09", "19/09", "23/09", "25/09"];
    closes = [46.85, 47.10, 47.45, 48.00, 48.90, 48.40, 47.95, 48.50, 48.20, base];
  }

  // Calcula SMA20 para o gráfico
  const sma20 = [];
  for (let i = 0; i < closes.length; i++) {
    if (i < 4 && closes.length < 20) {
      sma20.push(closes[i]);
    } else if (i < 19 && closes.length >= 20) {
      sma20.push(null);
    } else {
      const windowSize = Math.min(i + 1, 20);
      const slice = closes.slice(i - windowSize + 1, i + 1);
      sma20.push(+(slice.reduce((a, b) => a + b, 0) / windowSize).toFixed(2));
    }
  }

  const supVal = graficos.suporte || (closes[0] ? +(Math.min(...closes) * 0.98).toFixed(2) : 46.80);
  const resVal = graficos.resistencia || (closes[0] ? +(Math.max(...closes) * 1.02).toFixed(2) : 50.40);
  const suporteArr = new Array(closes.length).fill(supVal);
  const resistenciaArr = new Array(closes.length).fill(resVal);

  const canvasStock = document.getElementById("stockChart");
  if (canvasStock) {
    const ctxStock = canvasStock.getContext("2d");
    if (stockChartInstance) stockChartInstance.destroy();

    stockChartInstance = new Chart(ctxStock, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Preço de Fechamento (R$)",
            data: closes,
            borderColor: "#3B82F6",
            backgroundColor: "rgba(59, 130, 246, 0.12)",
            borderWidth: 2.5,
            tension: 0.2,
            fill: true,
            pointRadius: 3,
            pointBackgroundColor: "#3B82F6"
          },
          {
            label: "Média Móvel 20 (SMA)",
            data: sma20,
            borderColor: "#8B5CF6",
            borderWidth: 2,
            borderDash: [4, 4],
            tension: 0.2,
            pointRadius: 0,
            fill: false,
          },
          {
            label: "Suporte",
            data: suporteArr,
            borderColor: "#10B981",
            borderWidth: 1.5,
            borderDash: [2, 2],
            pointRadius: 0,
            fill: false,
          },
          {
            label: "Resistência",
            data: resistenciaArr,
            borderColor: "#EF4444",
            borderWidth: 1.5,
            borderDash: [2, 2],
            pointRadius: 0,
            fill: false,
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          x: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#64748B", font: { size: 10 } } },
          y: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#94A3B8", font: { size: 10 } } }
        }
      }
    });
  }

  // 2. Gráfico de Curva de Payoff de Opções
  let payoffData = graficos.payoff || [];
  if (!payoffData || payoffData.length === 0) {
    const sCompra = graficos.strike_compra || 48.50;
    const sVenda = graficos.strike_venda || 50.50;
    const debito = 0.85;
    payoffData = [];
    for (let p = +(sCompra - 4).toFixed(1); p <= +(sVenda + 4).toFixed(1); p = +(p + 0.5).toFixed(1)) {
      const ret = Math.max(0, p - sCompra) - Math.max(0, p - sVenda) - debito;
      payoffData.push({ preco_ativo: p, resultado_unitario: +ret.toFixed(2) });
    }
  }

  const canvasPayoff = document.getElementById("payoffChart");
  if (canvasPayoff && payoffData.length > 0) {
    const xLabels = payoffData.map(p => `R$ ${Number(p.preco_ativo).toFixed(2)}`);
    const yResults = payoffData.map(p => p.resultado_unitario);

    const ctxPayoff = canvasPayoff.getContext("2d");
    if (payoffChartInstance) payoffChartInstance.destroy();

    payoffChartInstance = new Chart(ctxPayoff, {
      type: "line",
      data: {
        labels: xLabels,
        datasets: [
          {
            label: "Resultado no Vencimento (R$/ação)",
            data: yResults,
            borderColor: "#00F0FF",
            backgroundColor: (context) => {
              const ctx = context.chart.ctx;
              const gradient = ctx.createLinearGradient(0, 0, 0, 250);
              gradient.addColorStop(0, "rgba(16, 185, 129, 0.4)");
              gradient.addColorStop(0.5, "rgba(0, 240, 255, 0.1)");
              gradient.addColorStop(1, "rgba(239, 68, 68, 0.4)");
              return gradient;
            },
            borderWidth: 3,
            fill: true,
            tension: 0.1,
            pointBackgroundColor: "#00F0FF",
            pointRadius: 4,
          },
          {
            label: "Zero Breakeven",
            data: new Array(yResults.length).fill(0),
            borderColor: "rgba(255, 255, 255, 0.3)",
            borderWidth: 1,
            borderDash: [3, 3],
            pointRadius: 0,
            fill: false
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (context) => `Resultado: R$ ${context.parsed.y.toFixed(2)} por ação`
            }
          }
        },
        scales: {
          x: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#64748B", font: { size: 10 } } },
          y: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#94A3B8", font: { size: 10 } } }
        }
      }
    });
  }
}

// ========================================================
// GERENCIAMENTO DA TRIAGEM & RANKING DOS 100 ATIVOS
// ========================================================
async function carregarRanking() {
  try {
    const res = await fetch("/api/ranking");
    const data = await res.json();
    if (data.status === "sucesso" && Array.isArray(data.ranking)) {
      todosDadosRanking = data.ranking;
      
      const stats = data.estatisticas || {};
      const elTotal = document.getElementById("statTotalTriados");
      const elAprov = document.getElementById("statAprovadas");
      const elVeto = document.getElementById("statVetadosRisco");
      const elElim = document.getElementById("statEliminadas");

      if (elTotal) elTotal.textContent = data.total || 100;
      if (elAprov) elAprov.textContent = stats.aprovados_ou_top_picks || 5;
      if (elVeto) elVeto.textContent = stats.vetados_gate_risco || 1;
      const totalElim = (stats.eliminados_tecnico || 0) + (stats.eliminados_fundamentalista || 0) + (stats.eliminados_macro || 0);
      if (elElim) elElim.textContent = totalElim || 95;

      renderizarTabelaRanking(todosDadosRanking);
    }
  } catch (err) {
    console.error("Erro ao carregar ranking dos 100 ativos:", err);
  }
}

function renderizarTabelaRanking(lista) {
  const tbody = document.getElementById("rankingTableBody");
  if (!tbody) return;
  tbody.innerHTML = "";

  if (lista.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; padding: 2rem; color: var(--text-muted);">Nenhum ativo encontrado para os filtros aplicados.</td></tr>`;
    return;
  }

  lista.forEach(item => {
    const tr = document.createElement("tr");
    if (item.posicao === 1) tr.classList.add("row-top1");
    if (item.status_funil === "VETADO_NO_RISCO") tr.classList.add("row-vetado");

    let rankBadgeClass = "rank-badge";
    if (item.posicao === 1) rankBadgeClass += " top-1";
    else if (item.posicao <= 5) rankBadgeClass += " top-5";

    let statusClass = "badge-funil";
    let statusTexto = item.status_funil;
    if (item.status_funil === "VETADO_NO_RISCO") {
      statusClass += " vetado";
      statusTexto = "🛡️ VETADO NO RISCO";
    } else if (item.status_funil === "ELEGIVEL_EM_ESPERA") {
      statusClass += " espera";
      statusTexto = "⏳ ELEGÍVEL / ESPERA";
    } else if (item.status_funil === "ELIMINADO_TECNICO") {
      statusClass += " tecnico";
      statusTexto = "📉 REPROV. TÉCNICO";
    } else if (item.status_funil === "ELIMINADO_FUNDAMENTALISTA") {
      statusClass += " fund";
      statusTexto = "📊 REPROV. VALUATION";
    } else if (item.status_funil === "ELIMINADO_MACRO") {
      statusClass += " macro";
      statusTexto = "🌐 REPROV. MACRO";
    }

    let scoreClass = "score-badge";
    if (item.score_geral >= 75) scoreClass += " score-high";
    else if (item.score_geral >= 60) scoreClass += " score-mid";
    else scoreClass += " score-low";

    tr.innerHTML = `
      <td style="text-align: center;"><span class="${rankBadgeClass}">#${item.posicao}</span></td>
      <td style="text-align: center;">
        <strong class="ticker-cell">${item.ticker}</strong>
        <div>
          <button class="quick-asset-btn" style="padding: 0.15rem 0.45rem; font-size: 0.68rem; margin-top: 3px;" onclick="verGraficoDoRanking('${item.ticker}')">📈 Gráfico</button>
        </div>
      </td>
      <td><strong>${item.empresa}</strong></td>
      <td style="color: var(--text-secondary);">${item.setor}</td>
      <td style="text-align: right; font-family: var(--font-mono);">${item.pl != null ? item.pl : '-'}</td>
      <td style="text-align: right; font-family: var(--font-mono);">${item.roe || '-'}</td>
      <td style="text-align: center;"><span style="font-size: 0.78rem;">${item.tendencia || '-'}</span></td>
      <td style="text-align: center;"><span class="${scoreClass}">${item.score_geral}</span></td>
      <td style="text-align: center;">
        <span class="${statusClass}">${statusTexto}</span>
        <div style="font-size: 0.68rem; color: var(--text-muted); margin-top: 3px;">${item.fase_eliminacao}</div>
      </td>
      <td class="motivo-cell">${item.motivo_detalhado}</td>
    `;
    tbody.appendChild(tr);
  });
}

function aplicarFiltroStatus(filtro, btnEl) {
  filtroStatusAtual = filtro;
  document.querySelectorAll(".ranking-filters-bar .filter-btn").forEach(b => b.classList.remove("active"));
  if (btnEl) btnEl.classList.add("active");
  filtrarTabelaRanking();
}

function filtrarTabelaRanking() {
  const inputEl = document.getElementById("rankingSearchInput");
  const termo = (inputEl ? inputEl.value : "").toLowerCase().trim();
  
  const filtrados = todosDadosRanking.filter(item => {
    let passaStatus = true;
    if (filtroStatusAtual === "top10") {
      passaStatus = item.posicao <= 10;
    } else if (filtroStatusAtual !== "todos") {
      passaStatus = item.status_funil === filtroStatusAtual;
    }

    if (!passaStatus) return false;

    if (!termo) return true;
    return (
      item.ticker.toLowerCase().includes(termo) ||
      item.empresa.toLowerCase().includes(termo) ||
      item.setor.toLowerCase().includes(termo) ||
      (item.motivo_detalhado && item.motivo_detalhado.toLowerCase().includes(termo)) ||
      (item.fase_eliminacao && item.fase_eliminacao.toLowerCase().includes(termo))
    );
  });

  renderizarTabelaRanking(filtrados);
}

function atualizarLogs(logs) {
  const consoleEl = document.getElementById("consoleLogs");
  if (!logs || logs.length === 0) return;

  if (logs.length !== ultimoLogCount) {
    consoleEl.innerHTML = "";
    logs.forEach(msg => {
      const line = document.createElement("div");
      line.className = "log-line";
      if (msg.includes("✅")) line.classList.add("text-success");
      else if (msg.includes("❌")) line.classList.add("text-warning");
      line.textContent = msg;
      consoleEl.appendChild(line);
    });
    consoleEl.scrollTop = consoleEl.scrollHeight;
    ultimoLogCount = logs.length;
  }
}

function limparLogs() {
  document.getElementById("consoleLogs").innerHTML = `<div class="log-line text-muted">[CONSOLE LIMPO]</div>`;
  ultimoLogCount = 0;
}

window.addEventListener("DOMContentLoaded", () => {
  verificarStatus();
  carregarRanking();
  trocarAba('deliberacao');
});

