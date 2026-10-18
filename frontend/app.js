/**
 * RippleGuard Frontend Application
 * Multi-Agent Change-Impact Intelligence Layer with FalkorDB
 */

let cy = null;
let currentScenarios = [];
let activeScenario = null;
let currentAnalysisResult = null;
let fullGraphData = null;

// Color mapping for node types
const NODE_COLORS = {
  Microservice: '#8b5cf6',
  CodeSymbol: '#3b82f6',
  ApiEndpoint: '#06b6d4',
  DbTable: '#14b8a6',
  DbColumn: '#0f766e',
  Workflow: '#f59e0b',
  TestCase: '#10b981',
  Team: '#6366f1',
  Engineer: '#818cf8',
  Incident: '#f43f5e',
  ADR: '#eab308',
  AgentMemory: '#a855f7'
};

const NODE_SHAPES = {
  Microservice: 'round-rectangle',
  CodeSymbol: 'ellipse',
  ApiEndpoint: 'diamond',
  DbTable: 'barrel',
  DbColumn: 'rectangle',
  Workflow: 'hexagon',
  TestCase: 'rectangle',
  Team: 'round-tag',
  Engineer: 'ellipse',
  Incident: 'triangle',
  ADR: 'round-diamond',
  AgentMemory: 'star'
};

// Initialize Application
document.addEventListener('DOMContentLoaded', async () => {
  initTabs();
  initModals();
  initCustomPrForm();
  initMobileViewSwitch();
  await checkSystemStatus();
  await loadPresetScenarios();
  await initCytoscapeGraph();

  // Auto-run first scenario (PR-104) on load for instant demonstration
  if (currentScenarios.length > 0) {
    selectScenario(currentScenarios[0]);
    setTimeout(() => {
      runAnalysis();
    }, 600);
  }
});

// Mobile View Switcher for Handheld Devices & Tablets
function initMobileViewSwitch() {
  const buttons = document.querySelectorAll('.mobile-view-btn');
  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      buttons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const view = btn.dataset.view;
      document.body.classList.remove('view-graph', 'view-intel', 'view-split');
      if (view === 'graph') {
        document.body.classList.add('view-graph');
      } else if (view === 'intel') {
        document.body.classList.add('view-intel');
      } else {
        document.body.classList.add('view-split');
      }
      if (cy) {
        setTimeout(() => {
          cy.resize();
          cy.fit(undefined, 30);
        }, 150);
      }
    });
  });

  // Auto resize Cytoscape on orientation change or window resize
  window.addEventListener('resize', () => {
    if (cy) {
      cy.resize();
    }
  });
}


// Check FalkorDB and System Status
async function checkSystemStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    const statusText = document.getElementById('falkorStatusText');
    const statsText = document.getElementById('graphStatsText');
    
    if (data.is_live_connected) {
      statusText.textContent = 'Live Server (Connected)';
      statusText.className = 'status-val text-emerald';
    } else {
      statusText.textContent = data.mode || 'FalkorDB Engine (Ready)';
      statusText.className = 'status-val text-cyan';
    }

    statsText.textContent = `${data.total_nodes} Nodes • ${data.total_edges} Edges`;
  } catch (err) {
    console.warn('Status fetch error:', err);
  }
}

// Initialize Cytoscape.js Graph Canvas
async function initCytoscapeGraph() {
  try {
    const res = await fetch('/api/graph');
    fullGraphData = await res.json();

    const cyElements = [];

    fullGraphData.nodes.forEach(n => {
      const type = n.data.type || 'CodeSymbol';
      let cleanLabel = n.data.label;
      if (type === 'CodeSymbol' && cleanLabel.includes('.')) {
        cleanLabel = cleanLabel.split('.').pop() + '()';
      } else if (type === 'AgentMemory') {
        cleanLabel = n.data.properties && n.data.properties.pr_id ? `Mem:${n.data.properties.pr_id}` : 'Mem';
      } else if (type === 'Incident') {
        cleanLabel = n.data.properties && n.data.properties.id ? n.data.properties.id : cleanLabel;
      } else if (type === 'TestCase') {
        cleanLabel = cleanLabel.replace('test_', '');
        if (cleanLabel.length > 15) cleanLabel = cleanLabel.substring(0, 14) + '..';
      } else if (cleanLabel.length > 18) {
        cleanLabel = cleanLabel.substring(0, 16) + '..';
      }

      cyElements.push({
        group: 'nodes',
        data: {
          id: n.data.id,
          label: cleanLabel,
          fullTitle: n.data.label,
          type: type,
          color: NODE_COLORS[type] || '#94a3b8',
          shape: NODE_SHAPES[type] || 'ellipse',
          rawProps: n.data.properties || {}
        }
      });
    });

    fullGraphData.edges.forEach(e => {
      cyElements.push({
        group: 'edges',
        data: {
          id: e.data.id,
          source: e.data.source,
          target: e.data.target,
          label: e.data.label || e.data.type,
          type: e.data.type
        }
      });
    });

    cy = cytoscape({
      container: document.getElementById('cy'),
      elements: cyElements,
      style: [
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'color': '#cbd5e1',
            'font-family': 'Inter, sans-serif',
            'font-size': '9px',
            'font-weight': 500,
            'text-valign': 'bottom',
            'text-margin-y': '5px',
            'text-max-width': '75px',
            'text-wrap': 'ellipsis',
            'background-color': 'data(color)',
            'shape': 'data(shape)',
            'width': '30px',
            'height': '30px',
            'border-width': '1.5px',
            'border-color': 'rgba(255, 255, 255, 0.25)',
            'text-outline-width': '2px',
            'text-outline-color': '#070b14',
            'transition-property': 'background-color, border-color, border-width, opacity, width, height',
            'transition-duration': '0.3s'
          }
        },
        {
          selector: 'node[type = "Microservice"]',
          style: {
            'width': '42px',
            'height': '42px',
            'border-color': '#a855f7',
            'border-width': '2.5px',
            'font-weight': 700,
            'color': '#e2e8f0'
          }
        },
        {
          selector: 'node[type = "Incident"]',
          style: {
            'width': '34px',
            'height': '34px',
            'border-color': '#f43f5e',
            'border-width': '2.5px',
            'font-weight': 700,
            'color': '#fca5a5'
          }
        },
        {
          selector: 'node[type = "Workflow"]',
          style: {
            'width': '38px',
            'height': '38px',
            'border-color': '#f59e0b',
            'border-width': '2px',
            'font-weight': 700,
            'color': '#fef08a'
          }
        },
        {
          selector: 'edge',
          style: {
            'width': 1.5,
            'line-color': 'rgba(255, 255, 255, 0.12)',
            'target-arrow-color': 'rgba(255, 255, 255, 0.2)',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'arrow-scale': 0.7,
            'font-size': '7px',
            'color': '#475569',
            'text-rotation': 'autorotate',
            'text-margin-y': '-5px',
            'transition-property': 'line-color, target-arrow-color, width, opacity',
            'transition-duration': '0.3s'
          }
        },
        // Blast radius highlight styles
        {
          selector: '.blast-seed',
          style: {
            'border-color': '#38bdf8',
            'border-width': '4px',
            'background-color': '#0284c7',
            'width': '44px',
            'height': '44px',
            'font-size': '11px',
            'font-weight': 700,
            'color': '#38bdf8',
            'z-index': 999,
            'shadow-blur': '20px',
            'shadow-color': '#38bdf8',
            'shadow-opacity': 0.8
          }
        },
        {
          selector: '.blast-impacted',
          style: {
            'border-color': '#f43f5e',
            'border-width': '3px',
            'opacity': 1.0,
            'font-size': '10px',
            'font-weight': 700,
            'color': '#ffffff',
            'z-index': 990,
            'shadow-blur': '12px',
            'shadow-color': 'rgba(244, 63, 94, 0.6)'
          }
        },
        {
          selector: '.blast-path-edge',
          style: {
            'line-color': '#f43f5e',
            'target-arrow-color': '#f43f5e',
            'width': 3,
            'opacity': 1.0,
            'shadow-blur': '8px',
            'shadow-color': '#f43f5e',
            'z-index': 980
          }
        },
        {
          selector: '.dimmed',
          style: {
            'opacity': 0.12
          }
        }
      ],
      layout: {
        name: 'cose',
        animate: true,
        randomize: false,
        nodeRepulsion: 18000,
        idealEdgeLength: 110,
        edgeElasticity: 0.45,
        gravity: 0.2,
        numIter: 400,
        nodeDimensionsIncludeLabels: true
      }

    });

    // Node click inspector listener
    cy.on('tap', 'node', function(evt) {
      const node = evt.target;
      openNodeInspector(node);
    });

    // Canvas background click clears inspector
    cy.on('tap', function(evt) {
      if (evt.target === cy) {
        closeNodeInspector();
      }
    });

    // Toolbar buttons
    document.getElementById('btnFitGraph').addEventListener('click', () => {
      cy.fit(undefined, 30);
    });

    document.getElementById('btnLayoutCose').addEventListener('click', () => {
      cy.layout({
        name: 'cose',
        animate: true,
        nodeRepulsion: 7000,
        idealEdgeLength: 70
      }).run();
    });

    document.getElementById('btnResetHighlight').addEventListener('click', () => {
      resetGraphHighlights();
    });

  } catch (err) {
    console.error('Failed to initialize Cytoscape graph:', err);
  }
}

// Reset Graph Highlights
function resetGraphHighlights() {
  if (!cy) return;
  cy.elements().removeClass('blast-seed blast-impacted blast-path-edge dimmed');
  document.getElementById('canvasFilterIndicator').textContent = `Showing all ${fullGraphData ? fullGraphData.nodes.length : 52} nodes`;
}

// Highlight Blast Radius Subgraph
function highlightBlastRadius(blastNodes, blastEdges, seedNodeIds) {
  if (!cy) return;
  resetGraphHighlights();

  const impactedNodeIds = new Set(blastNodes.map(n => n.id));
  const seedSet = new Set(seedNodeIds);

  // Dim non-impacted elements
  cy.elements().forEach(ele => {
    if (ele.isNode()) {
      if (seedSet.has(ele.id())) {
        ele.addClass('blast-seed');
      } else if (impactedNodeIds.has(ele.id())) {
        ele.addClass('blast-impacted');
      } else {
        ele.addClass('dimmed');
      }
    } else if (ele.isEdge()) {
      const src = ele.data('source');
      const tgt = ele.data('target');
      if (impactedNodeIds.has(src) && impactedNodeIds.has(tgt)) {
        ele.addClass('blast-path-edge');
      } else {
        ele.addClass('dimmed');
      }
    }
  });

  document.getElementById('canvasFilterIndicator').textContent = 
    `Blast Radius: ${impactedNodeIds.size} impacted nodes, ${seedSet.size} seed changes`;

  // Focus view on impacted elements
  const activeEles = cy.elements().filter('.blast-seed, .blast-impacted');
  if (activeEles.length > 0) {
    cy.animate({
      fit: { eles: activeEles, padding: 50 },
      duration: 600
    });
  }
}

// Open Node Inspector Drawer
function openNodeInspector(node) {
  const drawer = document.getElementById('nodeInspector');
  const typeBadge = document.getElementById('inspectorNodeType');
  const title = document.getElementById('inspectorNodeTitle');
  const body = document.getElementById('inspectorContent');

  const type = node.data('type');
  const label = node.data('label');
  const rawProps = node.data('rawProps') || {};

  typeBadge.textContent = type;
  typeBadge.style.backgroundColor = NODE_COLORS[type] || '#64748b';
  title.textContent = label;

  let html = '';
  // Outgoing relationships
  const outgoing = node.outgoers('edge');
  const incoming = node.incomers('edge');

  html += `<div class="inspector-prop-row">
    <div class="inspector-prop-key">Node ID</div>
    <div class="inspector-prop-val font-mono">${node.id()}</div>
  </div>`;

  for (const [key, val] of Object.entries(rawProps)) {
    if (key !== 'id' && key !== 'label') {
      html += `<div class="inspector-prop-row">
        <div class="inspector-prop-key">${key.replace(/_/g, ' ')}</div>
        <div class="inspector-prop-val font-mono">${typeof val === 'object' ? JSON.stringify(val) : val}</div>
      </div>`;
    }
  }

  // Relations summary
  html += `<hr style="border: 0; border-top: 1px solid rgba(255,255,255,0.08); margin: 14px 0;">`;
  html += `<div class="inspector-prop-row">
    <div class="inspector-prop-key">Downstream Calls (${outgoing.length})</div>`;
  outgoing.forEach(e => {
    html += `<div class="inspector-prop-val font-mono" style="font-size:0.75rem; margin-bottom:3px;">
      → <strong>${e.data('type')}</strong>: ${e.target().data('label')}
    </div>`;
  });
  html += `</div>`;

  html += `<div class="inspector-prop-row">
    <div class="inspector-prop-key">Upstream Callers (${incoming.length})</div>`;
  incoming.forEach(e => {
    html += `<div class="inspector-prop-val font-mono" style="font-size:0.75rem; margin-bottom:3px;">
      ← <strong>${e.data('type')}</strong>: ${e.source().data('label')}
    </div>`;
  });
  html += `</div>`;

  body.innerHTML = html;
  drawer.classList.remove('hidden');
}

function closeNodeInspector() {
  document.getElementById('nodeInspector').classList.add('hidden');
}
document.getElementById('btnCloseInspector').addEventListener('click', closeNodeInspector);

// Load Preset Scenarios
async function loadPresetScenarios() {
  try {
    const res = await fetch('/api/scenarios');
    currentScenarios = await res.json();
    const container = document.getElementById('scenarioChipsContainer');
    container.innerHTML = '';

    currentScenarios.forEach((sc, idx) => {
      const chip = document.createElement('div');
      chip.className = `scenario-chip ${idx === 0 ? 'active' : ''}`;
      chip.dataset.id = sc.id;

      let riskClass = 'critical';
      if (sc.expected_risk.includes('HIGH')) riskClass = 'high';
      if (sc.expected_risk.includes('LOW')) riskClass = 'low';

      chip.innerHTML = `
        <strong>${sc.pr_id}</strong>
        <span>${sc.title.substring(0, 36)}...</span>
        <span class="chip-risk-tag ${riskClass}">${sc.expected_risk.split(' ')[0]}</span>
      `;

      chip.addEventListener('click', () => {
        selectScenario(sc);
      });

      container.appendChild(chip);
    });
  } catch (err) {
    console.error('Error loading scenarios:', err);
  }
}

// Select Scenario
function selectScenario(sc) {
  activeScenario = sc;
  document.querySelectorAll('.scenario-chip').forEach(c => {
    c.classList.toggle('active', c.dataset.id === sc.id);
  });
  // Hide custom PR form if showing preset
  document.getElementById('customPrSection').classList.add('hidden');
}

// Trigger Multi-Agent Analysis
async function runAnalysis() {
  const runBtn = document.getElementById('btnRunAnalysis');
  runBtn.disabled = true;
  runBtn.innerHTML = `
    <svg class="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M21 12a9 9 0 1 1-6.219-8.56"></path>
    </svg>
    <span>Agents Investigating...</span>
  `;

  let payload = null;
  const customSection = document.getElementById('customPrSection');
  if (!customSection.classList.contains('hidden')) {
    // Custom PR form
    payload = {
      pr_id: document.getElementById('customPrId').value.trim(),
      title: document.getElementById('customPrTitle').value.trim(),
      changed_symbols: [document.getElementById('customPrSymbolSelect').value],
      diff: document.getElementById('customPrDiff').value.trim()
    };
  } else if (activeScenario) {
    payload = {
      pr_id: activeScenario.pr_id,
      title: activeScenario.title,
      description: activeScenario.description,
      author: activeScenario.author,
      changed_symbols: activeScenario.changed_symbols,
      diff: activeScenario.diff
    };
  }

  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    currentAnalysisResult = data;
    renderAnalysisResults(data);
  } catch (err) {
    console.error('Analysis execution failed:', err);
    alert('Analysis failed: ' + err.message);
  } finally {
    runBtn.disabled = false;
    runBtn.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polygon points="5 3 19 12 5 21 5 3"></polygon>
      </svg>
      <span>Run Multi-Agent Analysis</span>
    `;
  }
}
document.getElementById('btnRunAnalysis').addEventListener('click', runAnalysis);

// Render Analysis Results Across UI
function renderAnalysisResults(data) {
  const inv = data.investigation;
  const risk = data.risk_analysis;
  const actions = data.action_results;

  // 1. Highlight Blast Radius in Cytoscape
  highlightBlastRadius(inv.blast_nodes, inv.blast_edges, data.pr_data.changed_symbols);

  // 2. Update Risk Gauge
  const score = risk.score;
  const tier = risk.tier;
  const scoreVal = document.getElementById('riskScoreValue');
  const scoreTier = document.getElementById('riskScoreTier');
  const gaugeBar = document.getElementById('gaugeProgress');

  scoreVal.textContent = score;
  scoreTier.textContent = tier;
  scoreTier.className = `gauge-tier ${tier.toLowerCase()}`;
  gaugeBar.className = `gauge-bar ${tier.toLowerCase()}`;

  // SVG dashoffset: 264 is circumference of r=42
  const offset = 264 - (score / 100) * 264;
  gaugeBar.style.strokeDashoffset = offset;

  // Quick stats
  document.getElementById('statServices').textContent = inv.services.length;
  document.getElementById('statApis').textContent = inv.apis.length;
  document.getElementById('statWorkflows').textContent = inv.workflows.length;
  document.getElementById('statIncidents').textContent = risk.incidents.length;

  // Titles
  const summaryTitle = document.getElementById('riskSummaryTitle');
  const summaryDesc = document.getElementById('riskSummaryDesc');
  if (tier === 'CRITICAL') {
    summaryTitle.textContent = 'Catastrophic Blast Radius Detected';
    summaryDesc.textContent = `Direct topological reach into Tier-0 revenue checkout and prior ${risk.incidents[0]?.incident?.loss || '$320,000'} outage root cause. Dual lead approval required.`;
  } else if (tier === 'HIGH') {
    summaryTitle.textContent = 'High Operational & Concurrency Risk';
    summaryDesc.textContent = 'Touches core workflow and distributed locking/database schema. Staff signoff required.';
  } else if (tier === 'MEDIUM') {
    summaryTitle.textContent = 'Moderate Change Impact';
    summaryDesc.textContent = 'Standard downstream services affected. Automated regression tests must verify.';
  } else {
    summaryTitle.textContent = 'Safe & Contained Impact';
    summaryDesc.textContent = 'Low blast radius with zero critical revenue workflow intersection. Auto-approved for deployment.';
  }

  // 3. Update 4-Factor Breakdown
  const b = risk.breakdown;
  document.getElementById('scoreFactorWorkflow').textContent = `${b.workflow_criticality} / 30`;
  document.getElementById('barFactorWorkflow').style.width = `${(b.workflow_criticality / 30) * 100}%`;

  document.getElementById('scoreFactorIncident').textContent = `${b.incident_history} / 25`;
  document.getElementById('barFactorIncident').style.width = `${(b.incident_history / 25) * 100}%`;

  document.getElementById('scoreFactorReach').textContent = `${b.blast_reach} / 25`;
  document.getElementById('barFactorReach').style.width = `${(b.blast_reach / 25) * 100}%`;

  document.getElementById('scoreFactorAdr').textContent = `${b.adr_governance} / 20`;
  document.getElementById('barFactorAdr').style.width = `${(b.adr_governance / 20) * 100}%`;

  // 4. Update Stakeholders
  const stakeholderContainer = document.getElementById('stakeholderList');
  stakeholderContainer.innerHTML = '';
  const teams = actions.stakeholders.teams || [];
  teams.forEach(t => {
    const badge = document.createElement('div');
    badge.className = 'team-badge';
    badge.innerHTML = `
      <span class="team-name">${t.name}</span>
      <span class="team-channel">${t.slack || '#general'}</span>
      <span class="team-lead">Lead: ${t.lead || 'Tech Lead'}</span>
    `;
    stakeholderContainer.appendChild(badge);
  });

  // 5. Update Agent Traces Timeline
  renderAgentTraces(data.agent_traces);

  // 6. Update Smart Tests
  renderSmartTests(actions.test_selection, actions.test_run_results);

  // 7. Update Explainable Paths
  renderExplainablePaths(risk.explainable_paths);

  // 8. Safe Approval Gate Banner
  const gate = actions.gate_decision;
  const banner = document.getElementById('safeGateBanner');
  if (gate.requires_human_approval) {
    banner.classList.remove('hidden');
    document.getElementById('gateStatusText').textContent = gate.gate_status;
    document.getElementById('gateReasonText').textContent = gate.reasons.join(' ');
  } else {
    banner.classList.add('hidden');
  }
}

// Render Step-by-Step Agent Trace Timeline
function renderAgentTraces(traces) {
  const container = document.getElementById('agentTraceTimeline');
  document.getElementById('traceStepCount').textContent = traces.length;
  container.innerHTML = '';

  traces.forEach(step => {
    const card = document.createElement('div');
    let agentClass = 'investigator';
    if (step.agent.includes('Risk')) agentClass = 'risk';
    if (step.agent.includes('Action')) agentClass = 'action';

    card.className = `timeline-step ${agentClass}`;

    let codeboxHtml = '';
    if (step.tool) {
      codeboxHtml = `<div class="step-codebox">
        [MCP TOOL CALL] → <strong>${step.tool}</strong>(${JSON.stringify(step.arguments)})
      </div>`;
    }

    card.innerHTML = `
      <div class="step-header">
        <span class="step-agent ${agentClass}">${step.agent}</span>
        <span class="step-phase">${step.phase}</span>
      </div>
      <div class="step-message">${step.message}</div>
      ${codeboxHtml}
    `;
    container.appendChild(card);
  });
}

// Render Smart Tests Panel
function renderSmartTests(selection, runResults) {
  const list = document.getElementById('testItemsList');
  const selCount = selection.selected_tests ? selection.selected_tests.length : 0;
  document.getElementById('selectedTestCount').textContent = selCount;
  document.getElementById('ciSavingsText').textContent = 
    `Graph-guided smart selection: ${selCount} of ${selection.total_suite_count} tests selected (${selection.ci_reduction_percentage}% CI execution savings)`;

  list.innerHTML = '';

  const resultsMap = {};
  if (runResults && runResults.results) {
    runResults.results.forEach(r => {
      resultsMap[r.file] = r;
    });
  }

  (selection.selected_tests || []).forEach(item => {
    const testNode = item.test_node;
    const runInfo = resultsMap[testNode.file] || { passed: true, duration_ms: testNode.duration_ms || 40 };

    const card = document.createElement('div');
    card.className = 'test-card-item';
    card.innerHTML = `
      <div class="test-card-info">
        <span class="test-card-name">${testNode.name}</span>
        <span class="test-card-meta">${testNode.file} • Category: ${testNode.category} • Covers: ${item.target_covered.join(', ')}</span>
      </div>
      <div style="display:flex; align-items:center; gap:10px;">
        <span class="font-mono text-muted" style="font-size:0.75rem;">${runInfo.duration_ms || 35}ms</span>
        <span class="badge ${runInfo.passed ? 'text-emerald' : 'text-rose'}" style="background:${runInfo.passed ? 'rgba(16,185,129,0.15)' : 'rgba(244,63,94,0.15)'}">
          ${runInfo.passed ? 'PASSED ✓' : 'FAILED ✗'}
        </span>
      </div>
    `;
    list.appendChild(card);
  });
}

// Render Explainable Paths
function renderExplainablePaths(paths) {
  const container = document.getElementById('explainablePathsList');
  container.innerHTML = '';

  if (!paths || paths.length === 0) {
    container.innerHTML = `<div class="text-muted" style="font-size:0.8rem;">No critical paths intersected.</div>`;
    return;
  }

  paths.forEach(p => {
    const card = document.createElement('div');
    card.className = 'path-card';

    let stepsHtml = '';
    (p.steps || []).forEach((step, idx) => {
      stepsHtml += `
        <span class="path-node">${step.from.name || step.from.id}</span>
        <span class="path-arrow">-[${step.relation}]-></span>
      `;
      if (idx === p.steps.length - 1) {
        stepsHtml += `<span class="path-node" style="color:var(--accent-rose);">${step.to.name || step.to.id}</span>`;
      }
    });

    card.innerHTML = `
      <div style="font-size:0.75rem; font-weight:700; color:var(--text-dim); text-transform:uppercase;">
        Path Reach (Hop Length: ${p.length})
      </div>
      <div class="path-trail">${stepsHtml}</div>
    `;
    container.appendChild(card);
  });
}

// Safe Gate Approval Actions
document.getElementById('btnApproveGate').addEventListener('click', async () => {
  if (!currentAnalysisResult) return;
  const prId = currentAnalysisResult.pr_data.pr_id;
  const sessionId = currentAnalysisResult.session_id;

  try {
    const res = await fetch('/api/gate/decision', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        pr_id: prId,
        session_id: sessionId,
        decision: 'APPROVED',
        approver: 'Sarah Chen (Payments Staff Lead)',
        notes: 'Manual signoff provided after verifying backwards compatibility and running target regression suite.'
      })
    });
    const data = await res.json();
    alert(`Safe Gate: Deployment APPROVED for ${prId}. Audit record written to FalkorDB memory.`);
    document.getElementById('safeGateBanner').classList.add('hidden');
    checkSystemStatus();
  } catch (err) {
    alert('Approval submission error: ' + err.message);
  }
});

document.getElementById('btnRejectGate').addEventListener('click', async () => {
  if (!currentAnalysisResult) return;
  const prId = currentAnalysisResult.pr_data.pr_id;
  const sessionId = currentAnalysisResult.session_id;

  try {
    await fetch('/api/gate/decision', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        pr_id: prId,
        session_id: sessionId,
        decision: 'REJECTED',
        approver: 'Marcus Vance (Principal Architect)',
        notes: 'Rejected due to risk of checkout dropout regression. Requires dual-write transition period.'
      })
    });
    alert(`Safe Gate: PR ${prId} REJECTED. Decision logged to FalkorDB.`);
    document.getElementById('safeGateBanner').classList.add('hidden');
    checkSystemStatus();
  } catch (err) {
    alert('Rejection error: ' + err.message);
  }
});

// Tab Navigation
function initTabs() {
  document.querySelectorAll('.intel-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.intel-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

      tab.classList.add('active');
      const targetId = tab.dataset.tab;
      document.getElementById(targetId).classList.add('active');
    });
  });
}

// Custom PR Form Toggle
function initCustomPrForm() {
  const toggleBtn = document.getElementById('btnToggleCustomPr');
  const closeBtn = document.getElementById('btnCloseCustomPr');
  const panel = document.getElementById('customPrSection');

  toggleBtn.addEventListener('click', () => {
    panel.classList.toggle('hidden');
    document.querySelectorAll('.scenario-chip').forEach(c => c.classList.remove('active'));
    activeScenario = null;
  });

  closeBtn.addEventListener('click', () => {
    panel.classList.add('hidden');
    if (currentScenarios.length > 0) {
      selectScenario(currentScenarios[0]);
    }
  });
}

// Modals: Cypher Console and Graph Memory
function initModals() {
  // Cypher Modal
  const cypherModal = document.getElementById('cypherModal');
  document.getElementById('btnCypherModal').addEventListener('click', () => {
    cypherModal.classList.remove('hidden');
  });
  document.getElementById('btnCloseCypherModal').addEventListener('click', () => {
    cypherModal.classList.add('hidden');
  });

  // Memory Modal
  const memoryModal = document.getElementById('memoryModal');
  document.getElementById('btnMemoryModal').addEventListener('click', async () => {
    memoryModal.classList.remove('hidden');
    await loadCrossSessionMemories();
  });
  document.getElementById('btnCloseMemoryModal').addEventListener('click', () => {
    memoryModal.classList.add('hidden');
  });

  // Cypher Execution
  document.getElementById('btnExecuteCypher').addEventListener('click', async () => {
    const cypher = document.getElementById('cypherInput').value.trim();
    if (!cypher) return;

    const timeLabel = document.getElementById('cypherExecTime');
    timeLabel.textContent = 'Executing...';

    try {
      const res = await fetch('/api/query/cypher', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cypher })
      });
      const data = await res.json();
      timeLabel.textContent = `${data.duration_ms || 2}ms (${data.count} rows)`;

      // Render Table
      const headers = data.headers || ['result'];
      const rows = data.rows || [];

      const headTr = document.getElementById('cypherTableHeaders');
      headTr.innerHTML = headers.map(h => `<th>${h}</th>`).join('');

      const body = document.getElementById('cypherTableBody');
      body.innerHTML = rows.map(r => {
        return `<tr>${r.map(cell => `<td>${typeof cell === 'object' ? JSON.stringify(cell) : cell}</td>`).join('')}</tr>`;
      }).join('');
    } catch (err) {
      timeLabel.textContent = 'Error: ' + err.message;
    }
  });

  // Preset query buttons
  document.querySelectorAll('.chip-query').forEach(btn => {
    btn.addEventListener('click', () => {
      document.getElementById('cypherInput').value = btn.dataset.cypher;
      document.getElementById('btnExecuteCypher').click();
    });
  });
}

// Load Cross-Session Memories from FalkorDB
async function loadCrossSessionMemories() {
  const container = document.getElementById('memoryCardsList');
  container.innerHTML = '<div class="text-muted">Loading FalkorDB graph memories...</div>';

  try {
    const res = await fetch('/api/memory');
    const data = await res.json();
    container.innerHTML = '';

    if (data.memories.length === 0) {
      container.innerHTML = '<div class="text-muted">No memory records found.</div>';
      return;
    }

    data.memories.forEach(mem => {
      const card = document.createElement('div');
      card.className = 'memory-card';
      card.innerHTML = `
        <div class="memory-meta">
          <span><strong>${mem.pr_id || 'PR'}</strong> • ${mem.agent_role}</span>
          <span class="font-mono">${mem.created_at || 'Recent'}</span>
        </div>
        <div class="memory-summary">${mem.summary}</div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    container.innerHTML = '<div class="text-rose">Error loading memories: ' + err.message + '</div>';
  }
}
