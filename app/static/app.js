const $ = (id) => document.getElementById(id);
function node(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}
document.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(item => {
    const active = item === tab;
    item.classList.toggle('active', active);
    item.setAttribute('aria-pressed', String(active));
    $(item.dataset.panel).hidden = !active;
  });
}));
function rawResponse(data) {
  const details = node('details');
  details.append(node('summary', 'View complete JSON response'), node('pre', JSON.stringify(data, null, 2)));
  return details;
}
function safeLink(value) {
  try {
    const url = new URL(value);
    if (!['http:', 'https:'].includes(url.protocol)) return null;
    const a = node('a', 'Open published post ↗');
    a.href = url.href; a.target = '_blank'; a.rel = 'noopener noreferrer';
    return a;
  } catch { return null; }
}
function readable(key) { return key.replaceAll('_', ' ').replace(/^./, c => c.toUpperCase()); }
function list(items) {
  if (!items?.length) return node('p', 'None identified.', 'muted');
  const ul = node('ul', undefined, 'report-list');
  items.forEach(item => ul.append(node('li', item)));
  return ul;
}
function group(title, content) {
  const section = node('section', undefined, 'report-group');
  section.append(node('h3', title), typeof content === 'string' ? node('p', content) : content);
  return section;
}
function chips(items) {
  const wrap = node('div', undefined, 'chips');
  items.forEach(item => wrap.append(node('span', item, 'tag')));
  return wrap;
}
function table(headers, rows) {
  const wrap = node('div', undefined, 'table-wrap');
  const table = node('table'); const head = node('thead'); const tr = node('tr');
  headers.forEach(title => tr.append(node('th', title))); head.append(tr);
  const body = node('tbody');
  rows.forEach(row => {
    const tr = node('tr');
    row.forEach(value => {
      const td = node('td'); td.append(typeof value === 'string' ? document.createTextNode(value) : value); tr.append(td);
    });
    body.append(tr);
  });
  table.append(head, body); wrap.append(table); return wrap;
}
function renderAnalysis(data) {
  const root = $('analysis-result'); root.replaceChildren();
  const analysis = data.analysis; const competitor = analysis.competitor_analysis;
    const heading = node('div', undefined, 'report-heading');
  const identity = node('div');
  identity.append(node('p', 'WEBSITE REPORT', 'section-label'), node('h2', data.brand.name), node('p', data.brand.category, 'muted'));
  const source = node('div', undefined, 'report-source');
  source.append(node('span', data.metadata.source_url), node('span', `${data.metadata.elapsed_seconds}s · ${data.metadata.model}`));
  heading.append(identity, source); root.append(heading);

  const report = node('div', undefined, 'report');
  const nav = node('div', undefined, 'report-nav'); nav.setAttribute('role', 'tablist'); nav.setAttribute('aria-label', 'Analysis sections');
  const content = node('div', undefined, 'report-content');
  const panels = []; const buttons = [];
  function addPanel(id, title, subtitle) {
    const button = node('button', title, 'report-tab'); button.id = `tab-${id}`;
    button.setAttribute('role', 'tab'); button.setAttribute('aria-controls', `report-${id}`);
    const panel = node('section', undefined, 'report-panel'); panel.id = `report-${id}`;
    panel.setAttribute('role', 'tabpanel'); panel.setAttribute('aria-labelledby', button.id);
    panel.append(node('h3', title, 'panel-title'), node('p', subtitle, 'panel-description'));
    const index = panels.length; panels.push(panel); buttons.push(button);
    function activate(focus = false) {
      panels.forEach((item, i) => { item.hidden = i !== index; buttons[i].setAttribute('aria-selected', String(i === index)); buttons[i].tabIndex = i === index ? 0 : -1; });
      if (focus) button.focus();
    }
    button.addEventListener('click', () => activate());
    button.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % buttons.length;
      if (event.key === 'ArrowLeft') next = (index + buttons.length - 1) % buttons.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = buttons.length - 1;
      if (next !== undefined) { event.preventDefault(); buttons[next].click(); buttons[next].focus(); }
    });
    button.setAttribute('aria-selected', String(index === 0)); button.tabIndex = index === 0 ? 0 : -1;
    panel.hidden = index !== 0; nav.append(button); content.append(panel); return panel;
  }
  const overview = addPanel('overview', 'Overview', 'Business positioning and the opportunities identified from this website.');
  overview.append(node('p', data.brand.summary, 'lead'), group('Products & services', chips(data.brand.products_and_services)));
  const overviewGrid = node('div', undefined, 'report-columns');
  overviewGrid.append(group('Strengths', list(competitor.strengths)), group('Competitive advantages', list(competitor.competitive_advantages)), group('Opportunities', list(competitor.opportunities)));
  overview.append(overviewGrid);

  const competitors = addPanel('competitors', 'Competitors', 'Suggested competitors for further research. Names and comparisons are not independently verified.');
  competitors.append(node('p', competitor.brand_overview));
  if (competitor.competitors.length) {
    competitors.append(table(['Suggested competitor', 'Why it is relevant', 'Strengths', 'Potential gaps'], competitor.competitors.map(item => [item.name, item.rationale, list(item.strengths), list(item.weaknesses_or_gaps)])));
  } else competitors.append(node('p', 'No competitor suggestions were returned.', 'empty-state'));

  const queries = addPanel('queries', 'Search queries', 'Five search ideas across the supported platforms, with their intended audience and purpose.');
  queries.append(table(['Search query', 'Platforms', 'Intent & relevance', 'Audience'], analysis.target_search_queries.map(item => {
    const context = node('div'); context.append(node('p', item.intent), node('p', item.business_relevance, 'muted'));
    return [item.query, chips(item.platforms), context, item.target_audience];
  })));

  const seo = analysis.seo_improvements;
  const seoPanel = addPanel('seo', 'SEO', 'Recommended search presentation, keyword themes, and supporting content.');
  const preview = node('div', undefined, 'search-preview');
  preview.append(node('span', data.metadata.source_url, 'muted'), node('h4', seo.recommended_title), node('p', seo.meta_description));
  seoPanel.append(group('Suggested search appearance', preview), group('Title rationale', seo.title_rationale));
  const keywords = node('div', undefined, 'report-columns two');
  keywords.append(group('Primary keyword', chips([seo.primary_keyword])), group('Secondary keywords', chips(seo.secondary_keywords)), group('Long-tail keywords', list(seo.long_tail_keywords)), group('Business keywords', chips(seo.business_keywords)));
  seoPanel.append(keywords, group('Supporting content', list(seo.supporting_content)));

  const services = addPanel('services', 'Services', 'Website offerings and clearly labelled recommendations, with their supporting evidence.');
  analysis.top_services.forEach((item, index) => {
    const entry = node('article', undefined, 'service-entry');
    const heading = node('div', undefined, 'service-heading');
    heading.append(node('span', String(index + 1).padStart(2, '0'), 'row-number'), node('h4', item.name), node('span', item.evidence_type === 'observed' ? 'On website' : item.evidence_type === 'inferred_recommendation' ? 'Proposed offering' : 'Unverified AI output', item.evidence_type === 'observed' ? 'tag' : 'tag proposed'));
    entry.append(heading, node('p', item.description));
    const facts = node('dl', undefined, 'service-facts');
    [['Industry', item.target_industry], ['Customer', item.target_customer], ['Benefit', item.main_benefit]].forEach(([label, value]) => { const pair = node('div'); pair.append(node('dt', label), node('dd', value)); facts.append(pair); });
    entry.append(facts);
    if (item.source_quote) { const evidence = node('details', undefined, 'evidence'); evidence.append(node('summary', item.evidence_type === 'observed' ? 'Website evidence' : 'AI-generated quote � unverified'), node('blockquote', item.source_quote)); entry.append(evidence); }
    services.append(entry);
  });
  const audience = analysis.target_audience;
  const audiencePanel = addPanel('audience', 'Audience', 'Suggested customer segments, needs, and positioning.');
  const audienceGrid = node('div', undefined, 'report-columns two');
  const audienceLabels = {primary_audience: 'Primary audience', secondary_audience: 'Secondary audience', industries: 'Industries', business_types: 'Business types', customer_profiles: 'Customer profiles', geographical_focus: 'Geographical focus', customer_needs: 'Customer needs', interests: 'Interests', marketing_segments: 'Marketing segments'};
  Object.entries(audienceLabels).forEach(([key, label]) => audienceGrid.append(group(label, Array.isArray(audience[key]) ? list(audience[key]) : (audience[key] || 'Not established from the website.'))));
  audiencePanel.append(audienceGrid);
  report.append(nav, content); root.append(report);
  if (data.metadata.warnings.length) {
    const notes = node('details', undefined, 'report-notes');
    notes.append(node('summary', `Report notes (${data.metadata.warnings.length})`), list(data.metadata.warnings)); root.append(notes);
  }
  root.append(rawResponse(data)); root.hidden = false;
}
function renderPosting(data) {
  const root = $('posting-result'); root.replaceChildren();
  const grid = node('div', undefined, 'grid');
  data.results.forEach(result => {
    const card = node('article', undefined, 'card');
    card.append(node('h3', readable(result.platform)), node('span', readable(result.status), result.status === 'success' ? 'tag success' : 'tag error'));
    if (result.error) card.append(node('p', result.error, 'error'));
    if (result.posted_url) {
      const link = safeLink(result.posted_url);
      if (link) { const paragraph = node('p'); paragraph.append(link); card.append(paragraph); }
    }
    card.append(node('p', `Public access verified: ${result.public_access ? 'Yes' : 'No'}`));
    if (result.date) card.append(node('p', `${result.date} ${result.time || ''}`));
    grid.append(card);
  });
  root.append(grid, rawResponse(data)); root.hidden = false;
}
async function submit(form, endpoint, body, prefix, render) {
  const button = form.querySelector('button[type=submit]');
  const status = $(`${prefix}-status`); const result = $(`${prefix}-result`);
  button.disabled = true; status.className = 'status'; result.hidden = true;
  status.textContent = prefix === 'analysis' ? 'Reading website and preparing your analysis…' : 'Publishing… Please wait for every platform result.';
  try {
    const headers = {'Content-Type': 'application/json'};
    if ($('demo-key').value) headers['X-Demo-Key'] = $('demo-key').value;
    const response = await fetch(endpoint, { method: 'POST', headers, body: JSON.stringify(body) });
    let data;
    try { data = await response.json(); } catch { throw new Error('The server returned an unexpected response. It may be starting up; try again shortly.'); }
    if (!response.ok) {
      const detail = Array.isArray(data.detail) ? data.detail.map(item => item.msg).join('\n') : data.detail;
      throw new Error(data.error?.message || detail || `Request failed (${response.status}).`);
    }
    render(data);
    status.textContent = prefix === 'analysis' ? 'Analysis complete.' : `${data.results.filter(item => item.status === 'success').length} of ${data.results.length} platforms published successfully. Review each result below.`;
    status.className = 'status success';
    if (prefix === 'posting') $('confirm-publish').checked = false;
  } catch (error) { status.textContent = error.message; status.className = 'status error'; }
  finally { button.disabled = false; }
}
$('analysis-form').addEventListener('submit', event => {
  event.preventDefault(); submit(event.currentTarget, '/link-analysis', {url: $('website').value.trim()}, 'analysis', renderAnalysis);
});
$('message').addEventListener('input', () => {
  const length = Array.from($('message').value).length;
  $('character-count').textContent = `${length} / 200`;
  $('character-count').className = length > 200 ? 'error' : '';
  $('message').setCustomValidity(length > 200 ? 'Use at most 200 characters.' : '');
});
$('posting-form').addEventListener('submit', event => {
  event.preventDefault();
  const platforms = Array.from(document.querySelectorAll('#platform-options input:checked')).map(input => input.value);
  if (!platforms.length) {
    $('posting-status').textContent = 'Select at least one available platform.';
    $('posting-status').className = 'status error';
    return;
  }
  const picker = document.querySelector('.platform-picker');
  picker.disabled = true;
  submit(event.currentTarget, '/dashboard/posting', {message: $('message').value, platforms}, 'posting', renderPosting)
    .finally(() => { picker.disabled = false; });
});

async function loadPlatforms() {
  const root = $('platform-options');
  $('confirm-publish').checked = false;
  root.textContent = 'Loading platforms...';
  root.setAttribute('aria-busy', 'true');
  $('refresh-platforms').disabled = true;
  const labels = {mastodon: 'Mastodon', bluesky: 'Bluesky', wordpress: 'WordPress.com', tumblr: 'Tumblr', telegram: 'Telegram'};
  try {
    const response = await fetch('/dashboard/platforms');
    if (!response.ok) throw new Error('Could not load platforms. Please refresh.');
    const data = await response.json();
    root.replaceChildren();
    const updateSelection = () => {
      const count = root.querySelectorAll('input:checked').length;
      $('platform-selection-count').textContent = count ? `${count} selected` : 'No destinations selected';
    };
    data.platforms.forEach(item => {
      const label = node('label', undefined, 'platform-option');
      const input = node('input'); input.type = 'checkbox'; input.value = item.platform;
      input.disabled = !item.available;
      label.dataset.available = String(item.available);
      input.addEventListener('change', () => { $('confirm-publish').checked = false; updateSelection(); });
      const mark = node('span', {mastodon:'m', bluesky:'B', wordpress:'W', tumblr:'t', telegram:'T'}[item.platform], 'platform-mark');
      mark.setAttribute('aria-hidden', 'true');
      const text = node('span', undefined, 'platform-info');
      text.append(node('strong', labels[item.platform] || item.platform), node('small', item.available ? 'Configured' : item.reason));
      label.append(mark, text, input); root.append(label);
    });
    updateSelection();
  } catch (error) { root.textContent = error.message; }
  finally { $('refresh-platforms').disabled = false; root.setAttribute('aria-busy', 'false'); }
}
$('refresh-platforms').addEventListener('click', loadPlatforms);
loadPlatforms();
