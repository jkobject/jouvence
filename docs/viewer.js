(() => {
  'use strict';

  const SESSION_TOKEN_KEY = 'jouvence-viewer-session-token';
  const bootParams = new URLSearchParams(location.hash.replace(/^#/, ''));
  const bootstrapToken = bootParams.get('token') || '';
  if (bootstrapToken) {
    sessionStorage.setItem(SESSION_TOKEN_KEY, bootstrapToken);
    bootParams.delete('token');
    const cleanHash = bootParams.toString();
    history.replaceState(history.state, '', `${location.pathname}${location.search}${cleanHash ? `#${cleanHash}` : ''}`);
  }
  const SESSION_TOKEN = bootstrapToken || sessionStorage.getItem(SESSION_TOKEN_KEY) || '';
  const TYPE_LABEL = {gene:'GN',disease:'DS',molecule:'MO',phenotype:'PH'};
  const $ = selector => document.querySelector(selector);
  const $$ = selector => [...document.querySelectorAll(selector)];
  let current = null;
  let dossier = null;
  let trail = [];
  let searchItems = [];
  let searchIndex = -1;
  let searchGeneration = 0;
  let activeSearch = Promise.resolve();
  let toastTimer;
  let dataSource = null;

  function esc(value) { return String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
  function keyOf(type, id) { return `${type}:${id}`; }
  function typeGlyph(type) { return TYPE_LABEL[type] || type.slice(0,2).toUpperCase(); }
  function showToast(text){clearTimeout(toastTimer);const t=$('#toast');t.textContent=text;t.classList.add('show');toastTimer=setTimeout(()=>t.classList.remove('show'),2600);}
  function setSource(label, ok=true) { const pill=$('#source-button'); pill.innerHTML=`<span></span> ${esc(label)} <b>⌄</b>`; pill.classList.toggle('source-error', !ok); }

  async function checkedFetch(path, options = {}) {
    const headers = {...(options.headers || {})};
    if (SESSION_TOKEN && path.startsWith('/api')) headers['x-jouvence-session'] = SESSION_TOKEN;
    const response = await fetch(path, {...options, headers});
    if (!response.ok) {
      let detail = response.statusText;
      try { detail = (await response.json()).detail || detail; } catch (_) {}
      throw new Error(`${response.status}: ${detail}`);
    }
    return response;
  }
  async function fetchJson(path) { return (await checkedFetch(path)).json(); }

  function fixtureSearch(nodes, q, limit=10) {
    const needle = q.trim().toLowerCase();
    const candidates = nodes.map(node => {
      const aliases = [{kind:'canonical_id',value:node.node_id,source:node.source},{kind:'display_name',value:node.display_name,source:node.source},...node.aliases];
      const alias = aliases.find(item => String(item.value).toLowerCase().includes(needle));
      if (!alias) return null;
      const value = String(alias.value).toLowerCase();
      const rank = value === needle ? 0 : value.startsWith(needle) ? 1 : 2;
      return {node_type:node.node_type,node_id:node.node_id,display_name:node.display_name,description:node.description,matched_alias:alias.value,alias_kind:alias.kind,source:alias.source,rank};
    }).filter(Boolean).sort((a,b)=>a.rank-b.rank||a.node_type.localeCompare(b.node_type)||a.display_name.localeCompare(b.display_name));
    return {meta:{snapshot_id:'fixture-v1',data_mode:'fixture-static',truncated:candidates.length>limit},results:candidates.slice(0,limit)};
  }

  class ApiDataSource {
    async connect() { this.session=await fetchJson('/api/session'); return this; }
    label() { return `${this.session.source.label} · ${this.session.snapshot.snapshot_id}`; }
    search(q,limit) { return fetchJson(`/api/search?q=${encodeURIComponent(q)}&limit=${limit}`); }
    async dossier(type,id) {
      const root=`/api/nodes/${encodeURIComponent(type)}/${encodeURIComponent(id)}`;
      const [node,features,edges,evidence,longRange,putative]=await Promise.all([fetchJson(root),fetchJson(`${root}/features`),fetchJson(`${root}/edges`),fetchJson(`${root}/evidence`),fetchJson(`${root}/long-range`),fetchJson(`${root}/putative`)]);
      return {node:node.node,features:features.rows,edges:edges.rows,evidence:evidence.rows,evidence_meta:evidence.meta,evidence_access:'complete-local',long_range:longRange.rows,putative_links:putative.rows,meta:node.meta};
    }
    evidencePage(type,id,cursor) { const root=`/api/nodes/${encodeURIComponent(type)}/${encodeURIComponent(id)}/evidence`; return fetchJson(`${root}?limit=10&cursor=${encodeURIComponent(cursor)}`); }
    export(request) { return checkedFetch('/api/export',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request)}); }
  }

  function staticDossier(result) {
    const evidenceMeta=result.evidence_meta || {total:result.evidence.length,returned:result.evidence.length,truncated:false,next_cursor:null};
    return {...result,evidence_meta:evidenceMeta,evidence_access:'static-summary'};
  }

  class StaticBundleDataSource {
    constructor(root='viewer-data') { this.root=root; }
    async connect() {
      this.manifest=await fetchJson(`${this.root}/manifest.json`);
      if (this.manifest.schema_version !== 'jouvence-viewer-static-v1' || !this.manifest.fixture_only) throw new Error('Unsupported or non-fixture static viewer manifest');
      this.searchShard=await fetchJson(`${this.root}/${this.manifest.search_shard}`);
      return this;
    }
    label() { return `Static fixture bundle · ${this.manifest.snapshot_id}`; }
    search(q,limit) { return Promise.resolve(fixtureSearch(this.searchShard.nodes,q,limit)); }
    dossier(type,id) {
      const shard=this.manifest.entity_shards[keyOf(type,id)];
      if (!shard) return Promise.reject(new Error('Unknown static fixture node'));
      return fetchJson(`${this.root}/${shard}`).then(staticDossier);
    }
  }

  class EmbeddedFixtureDataSource {
    async connect() {
      this.bundle=window.JOUVENCE_FIXTURE_BUNDLE;
      if (!this.bundle?.manifest?.fixture_only) throw new Error('Embedded fixture unavailable');
      return this;
    }
    label() { return `Embedded fixture fallback · ${this.bundle.manifest.snapshot_id}`; }
    search(q,limit) { return Promise.resolve(fixtureSearch(this.bundle.search.nodes,q,limit)); }
    dossier(type,id) {
      const result=this.bundle.entities[keyOf(type,id)];
      return result ? Promise.resolve(staticDossier(result)) : Promise.reject(new Error('Unknown embedded fixture node'));
    }
  }

  async function chooseDataSource() {
    const failures=[];
    if (location.protocol === 'http:' || location.protocol === 'https:') {
      for (const candidate of [new ApiDataSource(),new StaticBundleDataSource()]) {
        try { return await candidate.connect(); } catch (error) { failures.push(error.message); }
      }
    }
    try { return await new EmbeddedFixtureDataSource().connect(); }
    catch (error) { failures.push(error.message); throw new Error(failures.join('; ')); }
  }

  async function loadDossier(type, id) {
    return dataSource.dossier(type,id);
  }

  function nodeLink(label,type,id,via) {
    return `<a class="node-link js-node-link" href="#node_type=${encodeURIComponent(type)}&node_id=${encodeURIComponent(id)}" data-node-type="${esc(type)}" data-node-id="${esc(id)}" data-via="${esc(via)}"><span class="node-glyph">${esc(typeGlyph(type))}</span><span><strong>${esc(label)}</strong><small>${esc(id)}</small></span><b>→</b></a>`;
  }
  function miniLink(label,type,id,meta,via) { return `<a class="js-node-link" href="#node_type=${encodeURIComponent(type)}&node_id=${encodeURIComponent(id)}" data-node-type="${esc(type)}" data-node-id="${esc(id)}" data-via="${esc(via)}">${esc(label)}</a><small>${esc(id)} · ${esc(meta)}</small>`; }

  function groupBy(rows, key) { return rows.reduce((acc,row)=>{(acc[row[key]] ||= []).push(row); return acc;}, {}); }
  function renderFeatureCards(items) {
    if (!items.length) return '<article class="feature-card empty-state"><span>EMPTY</span><h3>No feature rows</h3><p>This fixture node has no rows for the bounded feature endpoint.</p><footer>honest empty state</footer></article>';
    return items.map(row=>`<article class="feature-card"><span>${esc(row.feature_kind).toUpperCase()} · ${esc(row.epistemic_kind)}</span><h3>${esc(row.value)}</h3><p>${esc(row.feature_key)}</p><footer>${esc(row.source)} · ${esc(row.release || dossier.meta.snapshot_id)}</footer></article>`).join('');
  }
  function renderConnections(items) {
    if (!items.length) return '<div class="empty-state">No observed direct edges returned by the bounded fixture endpoint.</div>';
    return Object.entries(groupBy(items,'relation')).map(([relation,group])=>`<section class="connection-group"><header><h3>${esc(relation.replaceAll('_',' '))}</h3><span>${group.length} observed${group.length && group[0].anchor_role ? ` · anchor role ${esc(group[0].anchor_role)}` : ''}</span></header><div class="node-links">${group.map(row=>nodeLink(row.neighbor_name,row.neighbor_type,row.neighbor_id,relation)).join('')}</div></section>`).join('');
  }
  function renderLongRange(items) {
    if (!items.length) return '<div class="empty-state">No ranked long-range rows for this fixture node.</div>';
    return Object.entries(groupBy(items,'target_type')).map(([family,group])=>`<article class="long-card"><header><h3>${esc(family)}</h3><span>TOP ${Math.min(5,group.length)} · ranked</span></header>${group.map((row,i)=>`<div class="rank-row"><span>${i+1}</span><div>${miniLink(row.target_name,row.target_type,row.target_id,`${row.path_length} hops · ${row.ranker_id}`,'ranked '+family)}<small>${esc(row.support_path)} · ${esc(row.caveats)}</small></div><b class="rank-score">${Number(row.score).toFixed(2)}</b></div>`).join('')}</article>`).join('');
  }
  function renderPutative(items) {
    if (!items.length) return '<div class="empty-state">No putative inferred links are enabled for this fixture node.</div>';
    return items.map(row=>`<details class="putative-row"><summary><span class="hypothesis-badge">HYPOTHESIS</span><span><strong>${miniLink(row.target_name,row.target_type,row.target_id,row.policy_class,'putative '+row.template_id)}</strong><small>${esc(row.policy_class)} · not observed</small></span><b>+</b></summary><div class="putative-detail"><div><span>TEMPLATE</span><p>${esc(row.template_id)}</p></div><div><span>SUPPORT PATH</span><p>${esc(row.support_path)}</p></div><div><span>CAVEAT</span><p>${esc(row.leakage_caveat)}</p></div></div></details>`).join('');
  }
  function renderEvidence(filter='all') {
    const evidence = dossier.evidence.filter(row => filter === 'all' || row.relation === filter);
    $('#evidence-body').innerHTML = evidence.length ? evidence.map(row=>`<tr><td><code>${esc(row.relation)}</code><br><small>${esc(row.row_kind || 'observed')}</small></td><td>${esc(row.source)}<br><small>${esc(row.source_dataset || '')}</small></td><td>${esc(row.predicate)}</td><td>${Number(row.evidence_score || 0).toFixed(2)}</td><td><a href="https://www.ncbi.nlm.nih.gov/search/all/?term=${encodeURIComponent(row.paper_id || row.source_record_id)}" target="_blank" rel="noopener">${esc(row.paper_id || row.source_record_id)}</a></td></tr>`).join('') : '<tr><td colspan="5">No evidence rows returned for this relation.</td></tr>';
  }
  function renderEvidenceState() {
    const meta=dossier.evidence_meta || {total:dossier.evidence.length,returned:dossier.evidence.length,truncated:false,next_cursor:null};
    const total=Number(meta.total ?? dossier.evidence.length);
    const returned=dossier.evidence.length;
    const complete=dossier.evidence_access === 'complete-local' && !meta.next_cursor;
    $('#evidence-scope').textContent=dossier.evidence_access === 'complete-local'
      ? 'Complete local evidence is available through bounded 10-row pages.'
      : 'Static top-evidence summary only; use the local installation for complete paginated evidence.';
    $('#evidence-state').textContent=`Returned ${returned} of ${total} · ${dossier.evidence_access === 'complete-local' ? (complete ? 'complete' : 'more available') : 'static summary'}`;
    $('#load-more-evidence').hidden=!(dossier.evidence_access === 'complete-local' && meta.next_cursor);
    $('#load-more-evidence').disabled=false;
  }
  async function loadMoreEvidence() {
    const button=$('#load-more-evidence');
    const cursor=dossier.evidence_meta?.next_cursor;
    if (!(dataSource instanceof ApiDataSource) || !cursor) return;
    const requestedDossier=dossier;
    const requestedNode=keyOf(current.node_type,current.node_id);
    button.disabled=true;
    try {
      const page=await dataSource.evidencePage(current.node_type,current.node_id,cursor);
      if (dossier !== requestedDossier || keyOf(current.node_type,current.node_id) !== requestedNode) return;
      dossier.evidence.push(...page.rows);
      dossier.evidence_meta={...page.meta,returned:dossier.evidence.length};
      const selected=$('#evidence-filter').value;
      const relations=[...new Set(dossier.evidence.map(row=>row.relation))];
      $('#evidence-filter').innerHTML='<option value="all">All relations</option>'+relations.map(r=>`<option value="${esc(r)}">${esc(r.replaceAll('_',' '))}</option>`).join('');
      $('#evidence-filter').value=relations.includes(selected) ? selected : 'all';
      renderEvidence($('#evidence-filter').value);
      renderEvidenceState();
    } catch (error) {
      if (dossier === requestedDossier && keyOf(current.node_type,current.node_id) === requestedNode) showToast(`Evidence page failed: ${error.message}`);
    } finally {
      if (dossier === requestedDossier && keyOf(current.node_type,current.node_id) === requestedNode) button.disabled=false;
    }
  }

  function renderTrail() {
    $('#history-list').innerHTML=trail.map((step,i)=>`<li class="history-step ${i===trail.length-1?'current':''}" data-history-index="${i}"><span>${esc(step.via)}</span><strong>${esc(step.display_name)}</strong><small>${esc(step.node_type)}:${esc(step.node_id)}</small></li>`).join('');
    $('#history-count').textContent=`${trail.length} node${trail.length===1?'':'s'}`;
    $$('.history-step').forEach(el=>el.addEventListener('click',async()=>{const i=Number(el.dataset.historyIndex);trail=trail.slice(0,i+1);await navigate(trail[i].node_type,trail[i].node_id,'history',trail[i].via,false);}));
  }

  async function render(type, id) {
    try {
      dossier = await loadDossier(type, id);
      current = dossier.node;
    } catch (error) {
      $('#entity-name').textContent = 'Node unavailable';
      $('#entity-description').textContent = `Could not load ${type}:${id}. ${error.message}`;
      showToast('Unknown or unavailable node.');
      return;
    }
    $('#entity-type').textContent = current.node_type.toUpperCase();
    $('#entity-source').textContent = `${current.source} · ${dossier.meta.snapshot_id || 'fixture-v1'} · ${dossier.meta.data_mode || 'fixture'}`;
    $('#entity-name').textContent = current.display_name;
    $('#entity-description').textContent = current.description;
    $('#entity-ids').innerHTML = [`<span><b>canonical</b> ${esc(current.node_id)}</span>`, ...current.aliases.map(alias => `<span><b>${esc(alias.kind)}</b> ${esc(alias.value)}</span>`)].join('');
    $('#stat-direct').textContent = dossier.edges.length;
    $('#stat-evidence').textContent = dossier.evidence_meta?.total ?? dossier.evidence.length;
    $('#stat-putative').textContent = dossier.putative_links.length;
    $('#feature-grid').innerHTML = renderFeatureCards(dossier.features);
    $('#connections-list').innerHTML = renderConnections(dossier.edges);
    $('#long-range-grid').innerHTML = renderLongRange(dossier.long_range);
    $('#putative-list').innerHTML = renderPutative(dossier.putative_links);
    const relations=[...new Set(dossier.evidence.map(row=>row.relation))];
    $('#evidence-filter').innerHTML='<option value="all">All relations</option>'+relations.map(r=>`<option value="${esc(r)}">${esc(r.replaceAll('_',' '))}</option>`).join('');
    renderEvidence('all');
    renderEvidenceState();
    renderTrail();
    bindNodeLinks();
    document.title=`${current.display_name} — Jouvence-Graph viewer`;
  }

  async function navigate(type, id, mode='link', via='linked node', push=true) {
    const loaded = await loadDossier(type, id).catch(error => { showToast(`Node load failed: ${error.message}`); return null; });
    if (!loaded) return;
    dossier = loaded; current = loaded.node;
    if (mode === 'search') trail = [{node_type:type,node_id:id,display_name:current.display_name,via:'Search start'}];
    else if (mode === 'history') { /* trail was already truncated */ }
    else if (trail.at(-1)?.node_id !== id || trail.at(-1)?.node_type !== type) trail.push({node_type:type,node_id:id,display_name:current.display_name,via});
    await render(type, id);
    if (push) history.pushState({node_type:type,node_id:id},'',`#node_type=${encodeURIComponent(type)}&node_id=${encodeURIComponent(id)}`);
    window.scrollTo({top:0,behavior:'smooth'});
  }
  function bindNodeLinks() { $$('.js-node-link').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();navigate(a.dataset.nodeType,a.dataset.nodeId,'link',a.dataset.via);})); }

  async function search(query) {
    const generation = ++searchGeneration;
    const q=query.trim();
    const box=$('#search-results');
    searchIndex = -1;
    if (!q) { searchItems=[];box.replaceChildren();box.hidden=true;$('#global-search').setAttribute('aria-expanded','false');return; }
    try {
      const payload = await dataSource.search(q,12);
      if (generation !== searchGeneration) return;
      searchItems = payload.results;
      box.innerHTML=searchItems.map((n,i)=>`<button class="search-result" role="option" data-search-index="${i}" aria-selected="false"><span class="mini-type">${esc(n.node_type.toUpperCase())}</span><span><strong>${esc(n.display_name)}</strong><small>${esc(n.alias_kind)}: ${esc(n.matched_alias)} · ${esc(n.description)}</small></span><code>${esc(n.node_id)}</code></button>`).join('') || '<div class="search-result"><span></span><span><strong>No fixture match</strong><small>Try BRCA1, TP53, breast cancer, EFO:0000305 or CHEMBL1201585.</small></span></div>';
      $$('[data-search-index]').forEach(b=>b.addEventListener('click',()=>{const item=searchItems[Number(b.dataset.searchIndex)];navigate(item.node_type,item.node_id,'search');box.hidden=true;$('#global-search').value='';}));
    } catch (error) {
      if (generation !== searchGeneration) return;
      searchItems = [];
      box.innerHTML=`<div class="search-result"><span></span><span><strong>Backend unavailable</strong><small>${esc(error.message)}. Start it with: uv run jouvence-viewer</small></span></div>`;
    }
    box.hidden=false; $('#global-search').setAttribute('aria-expanded','true');
  }
  async function waitForSearch(generation) {
    const pending=activeSearch;
    await pending;
    return generation === searchGeneration && pending === activeSearch;
  }
  function moveSearch(delta) {
    const buttons = $$('[data-search-index]');
    if (!buttons.length) return;
    searchIndex = (searchIndex + delta + buttons.length) % buttons.length;
    buttons.forEach((b,i)=>b.setAttribute('aria-selected', String(i===searchIndex)));
    buttons[searchIndex].focus();
  }

  async function exportDossier(kind) {
    const slug=current.display_name.toLowerCase().replace(/\W+/g,'-');
    if (kind === 'pdf') { window.print(); showToast('Print dialog opened — choose Save as PDF.'); return; }
    if (dataSource instanceof ApiDataSource) {
      const response = await dataSource.export({node_type:current.node_type,node_id:current.node_id,trail,format:kind === 'csv' ? 'csv' : 'markdown'});
      const blob = await response.blob();
      download(`${slug}-dossier.${kind === 'csv' ? 'zip' : 'md'}`, blob);
    } else if (kind === 'csv') {
      download(`${slug}-dossier.zip`, staticCsvZip());
    } else {
      download(`${slug}-dossier.md`, new Blob([staticMarkdown()], {type:'text/markdown'}));
    }
    showToast(`${kind.toUpperCase()} export created.`);
  }
  function staticMarkdown() {
    const evidenceMeta=dossier.evidence_meta || {total:dossier.evidence.length,returned:dossier.evidence.length,truncated:false};
    const lines=['---',`snapshot_id: ${dossier.meta.snapshot_id}`,`data_mode: ${dossier.meta.data_mode || 'fixture'}`,`node_type: ${current.node_type}`,`node_id: ${current.node_id}`,'ranker_versions: [fixture_path_ranker:v1]',`evidence_total: ${evidenceMeta.total}`,`evidence_returned: ${dossier.evidence.length}`,`evidence_truncated: ${Boolean(evidenceMeta.truncated)}`,'---','',`# ${current.display_name}`,'',current.description,'','## Identity',`- Canonical ID: \`${current.node_id}\``,`- Type: \`${current.node_type}\``,`- Source: ${current.source}`,'','## Features'];
    lines.push(...dossier.features.map(row=>`- ${row.feature_kind} / ${row.feature_key}: ${row.value} (${row.epistemic_kind}; ${row.source})`));
    lines.push('','## Direct observed edges',...dossier.edges.map(row=>`- observed \`${row.relation}\` → ${row.neighbor_name} (${row.neighbor_type}:${row.neighbor_id}); score=${row.score}`));
    lines.push('','## Evidence',`Evidence export: bounded summary — ${dossier.evidence.length} of ${evidenceMeta.total} rows; truncated: ${Boolean(evidenceMeta.truncated)}.`,...dossier.evidence.map(row=>`- observed \`${row.relation}\` ${row.source} / ${row.predicate} / ${row.source_record_id} / score=${row.evidence_score}`));
    lines.push('','## Long-range ranked connections',...dossier.long_range.map(row=>`- ranked ${row.target_type}:${row.target_id} ${row.target_name} score=${row.score} path=${row.support_path} caveat=${row.caveats}`));
    lines.push('','## Putative inferred links',...dossier.putative_links.map(row=>`- inferred ${row.target_type}:${row.target_id} ${row.target_name} (${row.policy_class}) template=${row.template_id} caveat=${row.leakage_caveat}`));
    lines.push('','## Navigation trail',...trail.map((row,index)=>`${index+1}. ${row.display_name} (${row.node_type}:${row.node_id}) — ${row.via}`));
    return `${lines.join('\n')}\n`;
  }
  function csvText(items) {
    if (!items.length) return '\n';
    const fields=[...new Set(items.flatMap(row=>Object.keys(row)))].sort();
    const quote=value=>`"${String(value == null ? '' : typeof value === 'object' ? JSON.stringify(value) : value).replaceAll('"','""')}"`;
    return `${[fields,...items.map(row=>fields.map(field=>row[field]))].map(row=>row.map(quote).join(',')).join('\r\n')}\r\n`;
  }
  const CRC_TABLE=Array.from({length:256},(_,n)=>{let c=n;for(let k=0;k<8;k++)c=(c&1)?0xedb88320^(c>>>1):c>>>1;return c>>>0;});
  function crc32(bytes) { let crc=0xffffffff;for(const byte of bytes)crc=CRC_TABLE[(crc^byte)&255]^(crc>>>8);return (crc^0xffffffff)>>>0; }
  function zipBytes(files) {
    const encoder=new TextEncoder(),locals=[],centrals=[];let offset=0;
    for (const [name,text] of Object.entries(files)) {
      const filename=encoder.encode(name),data=encoder.encode(text),crc=crc32(data);
      const local=new Uint8Array(30+filename.length+data.length),lv=new DataView(local.buffer);
      lv.setUint32(0,0x04034b50,true);lv.setUint16(4,20,true);lv.setUint16(6,0x800,true);lv.setUint16(8,0,true);lv.setUint16(10,0,true);lv.setUint16(12,33,true);lv.setUint32(14,crc,true);lv.setUint32(18,data.length,true);lv.setUint32(22,data.length,true);lv.setUint16(26,filename.length,true);filename.forEach((v,i)=>local[30+i]=v);data.forEach((v,i)=>local[30+filename.length+i]=v);locals.push(local);
      const central=new Uint8Array(46+filename.length),cv=new DataView(central.buffer);
      cv.setUint32(0,0x02014b50,true);cv.setUint16(4,20,true);cv.setUint16(6,20,true);cv.setUint16(8,0x800,true);cv.setUint16(10,0,true);cv.setUint16(12,0,true);cv.setUint16(14,33,true);cv.setUint32(16,crc,true);cv.setUint32(20,data.length,true);cv.setUint32(24,data.length,true);cv.setUint16(28,filename.length,true);cv.setUint32(42,offset,true);filename.forEach((v,i)=>central[46+i]=v);centrals.push(central);offset+=local.length;
    }
    const centralSize=centrals.reduce((n,row)=>n+row.length,0),end=new Uint8Array(22),ev=new DataView(end.buffer);
    ev.setUint32(0,0x06054b50,true);ev.setUint16(8,centrals.length,true);ev.setUint16(10,centrals.length,true);ev.setUint32(12,centralSize,true);ev.setUint32(16,offset,true);
    const output=new Uint8Array(offset+centralSize+end.length);let cursor=0;for(const part of [...locals,...centrals,end]){output.set(part,cursor);cursor+=part.length;}return output;
  }
  function staticCsvZip() {
    const evidenceMeta=dossier.evidence_meta || {total:dossier.evidence.length,returned:dossier.evidence.length,truncated:false};
    const files={
      'node.csv':csvText([dossier.node]),'features.csv':csvText(dossier.features),'edges.csv':csvText(dossier.edges),'evidence.csv':csvText(dossier.evidence),'long_range.csv':csvText(dossier.long_range),'putative_links.csv':csvText(dossier.putative_links),'history.csv':csvText(trail),
      'manifest.json':JSON.stringify({snapshot_id:dossier.meta.snapshot_id,data_mode:dossier.meta.data_mode || 'fixture',row_kinds:['observed','ranked','inferred'],evidence:{scope:'bounded-summary',total:evidenceMeta.total,returned:dossier.evidence.length,truncated:Boolean(evidenceMeta.truncated)}},null,2),
    };
    return new Blob([zipBytes(files)],{type:'application/zip'});
  }
  function download(name, blob) { const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;document.body.append(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove();},0); }

  function wireEvents() {
    $('#global-search').addEventListener('input',e=>{activeSearch=search(e.target.value);});
    $('#global-search').addEventListener('keydown',async e=>{if(e.key==='Escape'){searchGeneration+=1;activeSearch=Promise.resolve();searchItems=[];searchIndex=-1;$('#search-results').hidden=true;e.target.blur();} else if(e.key==='ArrowDown'){e.preventDefault();const generation=searchGeneration;if(await waitForSearch(generation))moveSearch(1);} else if(e.key==='ArrowUp'){e.preventDefault();const generation=searchGeneration;if(await waitForSearch(generation))moveSearch(-1);} else if(e.key==='Enter'){e.preventDefault();const generation=searchGeneration;if(!await waitForSearch(generation))return;const item=searchItems[Math.max(searchIndex,0)];if(item){navigate(item.node_type,item.node_id,'search');$('#search-results').hidden=true;e.target.value='';}}});
    document.addEventListener('keydown',e=>{if(e.key==='/'&&document.activeElement.tagName!=='INPUT'){e.preventDefault();$('#global-search').focus();}});
    document.addEventListener('click',e=>{if(!e.target.closest('.viewer-search-wrap'))$('#search-results').hidden=true;});
    $('#evidence-filter').addEventListener('change',e=>renderEvidence(e.target.value));
    $('#load-more-evidence').addEventListener('click',loadMoreEvidence);
    $('#clear-history').addEventListener('click',()=>{trail=[{node_type:current.node_type,node_id:current.node_id,display_name:current.display_name,via:'Trail cleared'}];renderTrail();});
    $$('[data-export]').forEach(b=>b.addEventListener('click',()=>exportDossier(b.dataset.export).catch(error=>showToast(`Export failed: ${error.message}`))));
    $$('[data-copy-section]').forEach(b=>b.addEventListener('click',async()=>{await navigator.clipboard.writeText(dossier.features.map(x=>`${x.feature_kind}: ${x.value} (${x.epistemic_kind}; ${x.source})`).join('\n'));showToast('Features copied.');}));
    const dialog=$('#source-dialog');
    $('#source-button').addEventListener('click',()=>dialog.showModal());
    $('#connect-source').addEventListener('click',e=>{const value=$('input[name=source]:checked').value;if(value!=='demo'){e.preventDefault();showToast('Data source is fixed at launch. Restart with the CLI command in the installation guide.');}else showToast('Fixture selected.');});
    window.addEventListener('popstate',()=>{const params=new URLSearchParams(location.hash.replace(/^#/, ''));const type=params.get('node_type'), id=params.get('node_id');if(type&&id)navigate(type,id,'history','Browser navigation',false);});
  }

  async function boot() {
    wireEvents();
    try {
      dataSource=await chooseDataSource();
      setSource(dataSource.label());
      const session=dataSource instanceof ApiDataSource ? dataSource.session : null;
      const staticMode=dataSource instanceof StaticBundleDataSource ? 'static subset' : 'embedded subset';
      $('#mode-status').textContent=session?.source.mode || staticMode;
      $('#snapshot-status').textContent=session?.snapshot.snapshot_id || dataSource.manifest?.snapshot_id || dataSource.bundle?.manifest.snapshot_id || 'fixture-v1';
      $('#cache-status').textContent=session?.cache.status || 'browser fixture';
      $('#cost-warning').textContent=session?.source.requester_pays_warning || (session ? 'Local read-only mode; no cloud charge.' : 'Public static subset only — follow the local installation guide for a reviewed full query bundle.');
      $('#cost-warning').hidden=false;
      if (dataSource instanceof EmbeddedFixtureDataSource) showToast('Using the generated embedded fixture because HTTP bundle loading is unavailable.');
    } catch (error) {
      setSource('Viewer data unavailable', false);
      $('#entity-name').textContent='Viewer data unavailable';
      $('#entity-description').textContent=`No API, static bundle, or embedded fixture could be loaded. ${error.message}`;
      return;
    }
    const params=new URLSearchParams(location.hash.replace(/^#/, ''));
    const type=params.get('node_type') || 'gene';
    const id=params.get('node_id') || 'ENSG00000012048';
    const first = await loadDossier(type,id).catch(()=>loadDossier('gene','ENSG00000012048'));
    trail=[{node_type:first.node.node_type,node_id:first.node.node_id,display_name:first.node.display_name,via:params.get('node_id') ? 'Direct URL' : 'Search start'}];
    await render(first.node.node_type, first.node.node_id);
  }

  boot();
})();
