(() => {
  'use strict';

  const API = (location.protocol === 'http:' || location.protocol === 'https:') ? location.origin : 'http://127.0.0.1:8765';
  const FALLBACK = location.protocol === 'file:' || location.hostname.endsWith('github.io') || location.hostname === 'www.jkobject.com';
  const TYPE_LABEL = {gene:'GN',disease:'DS',molecule:'MO',phenotype:'PH'};
  const $ = selector => document.querySelector(selector);
  const $$ = selector => [...document.querySelectorAll(selector)];
  let current = null;
  let dossier = null;
  let trail = [];
  let searchItems = [];
  let searchIndex = -1;
  let toastTimer;
  let apiMode = 'api';

  const DEMO = {
    nodes: {
      'gene:ENSG00000012048': {node_type:'gene',node_id:'ENSG00000012048',display_name:'BRCA1',description:'DNA repair associated protein 1; a tumor suppressor involved in homologous recombination and genome integrity.',source:'Ensembl fixture',aliases:[{kind:'symbol',value:'BRCA1',source:'HGNC fixture'},{kind:'external_id',value:'HGNC:1100',source:'HGNC fixture'},{kind:'external_id',value:'672',source:'NCBI Gene fixture'},{kind:'external_id',value:'P38398',source:'UniProt fixture'}],attributes:{biotype:'protein_coding',chromosome:'17q21.31'}},
      'gene:ENSG00000141510': {node_type:'gene',node_id:'ENSG00000141510',display_name:'TP53',description:'Tumor protein p53; a transcription factor coordinating DNA-damage responses, cell-cycle arrest and apoptosis.',source:'Ensembl fixture',aliases:[{kind:'symbol',value:'TP53',source:'HGNC fixture'},{kind:'external_id',value:'P04637',source:'UniProt fixture'}],attributes:{biotype:'protein_coding'}},
      'gene:ENSG00000146648': {node_type:'gene',node_id:'ENSG00000146648',display_name:'EGFR',description:'Epidermal growth factor receptor; a receptor tyrosine kinase involved in proliferation and survival signaling.',source:'Ensembl fixture',aliases:[{kind:'symbol',value:'EGFR',source:'HGNC fixture'},{kind:'external_id',value:'P00533',source:'UniProt fixture'}],attributes:{biotype:'protein_coding'}},
      'disease:EFO:0000305': {node_type:'disease',node_id:'EFO:0000305',display_name:'breast carcinoma',description:'A malignant neoplasm arising from breast tissue.',source:'OpenTargets fixture',aliases:[{kind:'name',value:'breast cancer',source:'EFO fixture'},{kind:'external_id',value:'MONDO:0007254',source:'MONDO fixture'}],attributes:{ontology:'EFO'}},
      'disease:EFO:0000616': {node_type:'disease',node_id:'EFO:0000616',display_name:'lung carcinoma',description:'A malignant neoplasm originating in lung tissue.',source:'OpenTargets fixture',aliases:[{kind:'name',value:'lung cancer',source:'EFO fixture'}],attributes:{ontology:'EFO'}},
      'molecule:CHEMBL1201585': {node_type:'molecule',node_id:'CHEMBL1201585',display_name:'gefitinib',description:'A small-molecule EGFR tyrosine kinase inhibitor.',source:'ChEMBL fixture',aliases:[{kind:'name',value:'IRESSA',source:'ChEMBL fixture'},{kind:'external_id',value:'DB00317',source:'DrugBank fixture'}],attributes:{chembl_phase:'4'}},
      'phenotype:HP:0003011': {node_type:'phenotype',node_id:'HP:0003011',display_name:'Abnormal cell proliferation',description:'A phenotype involving altered regulation or rate of cellular proliferation.',source:'HPO fixture',aliases:[{kind:'name',value:'abnormal proliferation',source:'HPO fixture'}],attributes:{ontology:'HPO'}}
    },
    features: {'gene:ENSG00000012048': [{feature_kind:'identity_summary',feature_key:'description',value:'DNA repair and homologous recombination context.',source:'fixture summaries',epistemic_kind:'source-backed'},{feature_kind:'model_context',feature_key:'fixture_embedding_family',value:'text-neighborhood-demo',source:'fixture ranker',epistemic_kind:'model/fallback'}]},
    edges: {'gene:ENSG00000012048': [
      {edge_key:'fixture:edge:1',relation:'disease_associated_gene',display_relation:'disease associated gene',neighbor_type:'disease',neighbor_id:'EFO:0000305',neighbor_name:'breast carcinoma',anchor_role:'x',source:'OpenTargets fixture',score:.92,row_kind:'observed'},
      {edge_key:'fixture:edge:9',relation:'gene_interacts_gene',display_relation:'gene interacts gene',neighbor_type:'gene',neighbor_id:'ENSG00000141510',neighbor_name:'TP53',anchor_role:'x',source:'BioGRID fixture',score:.79,row_kind:'observed'},
      {edge_key:'fixture:edge:10',relation:'molecule_targets_gene',display_relation:'molecule targets gene',neighbor_type:'molecule',neighbor_id:'CHEMBL1201585',neighbor_name:'gefitinib',anchor_role:'y',source:'ChEMBL fixture',score:.65,row_kind:'observed'}]},
    evidence: {'gene:ENSG00000012048': [{edge_key:'fixture:edge:1',relation:'disease_associated_gene',source:'OpenTargets fixture',predicate:'associated_with',evidence_score:.92,source_record_id:'fixture:ot:brca1-breast',paper_id:'PMID:0000001',row_kind:'observed'}]},
    long: {'gene:ENSG00000012048': [{target_type:'disease',target_id:'EFO:0000305',target_name:'breast carcinoma',score:.94,rank:1,ranker_id:'fixture_path_ranker',path_length:1,support_path:'BRCA1 → breast carcinoma',caveats:'Ranked context; not causal.',row_kind:'ranked'},{target_type:'molecule',target_id:'CHEMBL1201585',target_name:'gefitinib',score:.65,rank:1,ranker_id:'fixture_path_ranker',path_length:3,support_path:'BRCA1 → TP53 → EGFR → gefitinib',caveats:'Ranked retrieval only.',row_kind:'ranked'}]},
    putative: {'gene:ENSG00000012048': [{target_type:'disease',target_id:'EFO:0000616',target_name:'lung carcinoma',policy_class:'inferred_weak',template_id:'gene_disease_path_v1',support_path:'BRCA1 → TP53 → lung carcinoma',leakage_caveat:'Association path is not causal.',row_kind:'inferred'}]}
  };

  function esc(value) { return String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
  function keyOf(type, id) { return `${type}:${id}`; }
  function rows(map, type, id) { return map[keyOf(type,id)] || []; }
  function typeGlyph(type) { return TYPE_LABEL[type] || type.slice(0,2).toUpperCase(); }
  function showToast(text){clearTimeout(toastTimer);const t=$('#toast');t.textContent=text;t.classList.add('show');toastTimer=setTimeout(()=>t.classList.remove('show'),2600);}
  function setSource(label, ok=true) { const pill=$('#source-button'); pill.innerHTML=`<span></span> ${esc(label)} <b>⌄</b>`; pill.classList.toggle('source-error', !ok); }

  async function api(path, options = {}) {
    const response = await fetch(`${API}${path}`, options);
    if (!response.ok) {
      let detail = response.statusText;
      try { detail = (await response.json()).detail || detail; } catch (_) {}
      throw new Error(`${response.status}: ${detail}`);
    }
    return response;
  }
  async function json(path) { return (await api(path)).json(); }

  function fallbackSearch(q, limit=10) {
    const needle = q.trim().toLowerCase();
    const results = Object.values(DEMO.nodes).filter(n => [n.node_id,n.display_name,...n.aliases.map(a=>a.value)].some(v => String(v).toLowerCase().includes(needle))).slice(0, limit).map((n,i)=>({node_type:n.node_type,node_id:n.node_id,display_name:n.display_name,description:n.description,matched_alias:n.display_name,alias_kind:'fixture_fallback',source:n.source,rank:i}));
    return {meta:{snapshot_id:'fixture-v1',data_mode:'fixture-demo-fallback',truncated:false},results};
  }
  async function loadDossier(type, id) {
    if (apiMode === 'fallback') {
      const node = DEMO.nodes[keyOf(type,id)];
      if (!node) throw new Error('Unknown fixture fallback node');
      return {node,features:rows(DEMO.features,type,id),edges:rows(DEMO.edges,type,id),evidence:rows(DEMO.evidence,type,id),long_range:rows(DEMO.long,type,id),putative_links:rows(DEMO.putative,type,id),meta:{snapshot_id:'fixture-v1',data_mode:'fixture-demo-fallback'}};
    }
    const [node, features, edges, evidence, longRange, putative] = await Promise.all([
      json(`/api/nodes/${encodeURIComponent(type)}/${encodeURIComponent(id)}`),
      json(`/api/nodes/${encodeURIComponent(type)}/${encodeURIComponent(id)}/features`),
      json(`/api/nodes/${encodeURIComponent(type)}/${encodeURIComponent(id)}/edges`),
      json(`/api/nodes/${encodeURIComponent(type)}/${encodeURIComponent(id)}/evidence`),
      json(`/api/nodes/${encodeURIComponent(type)}/${encodeURIComponent(id)}/long-range`),
      json(`/api/nodes/${encodeURIComponent(type)}/${encodeURIComponent(id)}/putative`),
    ]);
    return {node:node.node,features:features.rows,edges:edges.rows,evidence:evidence.rows,long_range:longRange.rows,putative_links:putative.rows,meta:node.meta};
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
    $('#entity-source').textContent = `${current.source} · ${dossier.meta.snapshot_id || 'fixture-v1'} · ${dossier.meta.data_mode || apiMode}`;
    $('#entity-name').textContent = current.display_name;
    $('#entity-description').textContent = current.description;
    $('#entity-ids').innerHTML = [`<span><b>canonical</b> ${esc(current.node_id)}</span>`, ...current.aliases.map(alias => `<span><b>${esc(alias.kind)}</b> ${esc(alias.value)}</span>`)].join('');
    $('#stat-direct').textContent = dossier.edges.length;
    $('#stat-evidence').textContent = dossier.evidence.length;
    $('#stat-putative').textContent = dossier.putative_links.length;
    $('#feature-grid').innerHTML = renderFeatureCards(dossier.features);
    $('#connections-list').innerHTML = renderConnections(dossier.edges);
    $('#long-range-grid').innerHTML = renderLongRange(dossier.long_range);
    $('#putative-list').innerHTML = renderPutative(dossier.putative_links);
    const relations=[...new Set(dossier.evidence.map(row=>row.relation))];
    $('#evidence-filter').innerHTML='<option value="all">All relations</option>'+relations.map(r=>`<option value="${esc(r)}">${esc(r.replaceAll('_',' '))}</option>`).join('');
    renderEvidence('all');
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
    const q=query.trim();
    const box=$('#search-results');
    searchIndex = -1;
    if (!q) { box.hidden=true; $('#global-search').setAttribute('aria-expanded','false'); return; }
    try {
      const payload = apiMode === 'fallback' ? fallbackSearch(q,12) : await json(`/api/search?q=${encodeURIComponent(q)}&limit=12`);
      searchItems = payload.results;
      box.innerHTML=searchItems.map((n,i)=>`<button class="search-result" role="option" data-search-index="${i}" aria-selected="false"><span class="mini-type">${esc(n.node_type.toUpperCase())}</span><span><strong>${esc(n.display_name)}</strong><small>${esc(n.alias_kind)}: ${esc(n.matched_alias)} · ${esc(n.description)}</small></span><code>${esc(n.node_id)}</code></button>`).join('') || '<div class="search-result"><span></span><span><strong>No fixture match</strong><small>Try BRCA1, TP53, breast cancer, EFO:0000305 or CHEMBL1201585.</small></span></div>';
      $$('[data-search-index]').forEach(b=>b.addEventListener('click',()=>{const item=searchItems[Number(b.dataset.searchIndex)];navigate(item.node_type,item.node_id,'search');box.hidden=true;$('#global-search').value='';}));
    } catch (error) {
      box.innerHTML=`<div class="search-result"><span></span><span><strong>Backend unavailable</strong><small>${esc(error.message)}. Start it with: uv run jouvence-viewer</small></span></div>`;
    }
    box.hidden=false; $('#global-search').setAttribute('aria-expanded','true');
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
    if (apiMode === 'api') {
      const response = await api('/api/export', {method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({node_type:current.node_type,node_id:current.node_id,trail,format:kind === 'csv' ? 'csv' : 'markdown'})});
      const blob = await response.blob();
      download(`${slug}-dossier.${kind === 'csv' ? 'zip' : 'md'}`, blob);
    } else {
      const text = fallbackMarkdown();
      download(`${slug}-dossier.md`, new Blob([text], {type:'text/markdown'}));
    }
    showToast(`${kind.toUpperCase()} export created.`);
  }
  function fallbackMarkdown() { return `---\nsnapshot_id: fixture-v1\ndata_mode: fixture-demo-fallback\nnode: ${current.node_type}:${current.node_id}\n---\n\n# ${current.display_name}\n\n${current.description}\n\n## Navigation trail\n${trail.map((s,i)=>`${i+1}. ${s.display_name} (${s.node_type}:${s.node_id}) — ${s.via}`).join('\n')}\n`; }
  function download(name, blob) { const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;document.body.append(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove();},0); }

  function wireEvents() {
    $('#global-search').addEventListener('input',e=>search(e.target.value));
    $('#global-search').addEventListener('keydown',e=>{if(e.key==='Escape'){$('#search-results').hidden=true;e.target.blur();} else if(e.key==='ArrowDown'){e.preventDefault();moveSearch(1);} else if(e.key==='ArrowUp'){e.preventDefault();moveSearch(-1);} else if(e.key==='Enter'){const item=searchItems[Math.max(searchIndex,0)];if(item){navigate(item.node_type,item.node_id,'search');$('#search-results').hidden=true;e.target.value='';}}});
    document.addEventListener('keydown',e=>{if(e.key==='/'&&document.activeElement.tagName!=='INPUT'){e.preventDefault();$('#global-search').focus();}});
    document.addEventListener('click',e=>{if(!e.target.closest('.viewer-search-wrap'))$('#search-results').hidden=true;});
    $('#evidence-filter').addEventListener('change',e=>renderEvidence(e.target.value));
    $('#clear-history').addEventListener('click',()=>{trail=[{node_type:current.node_type,node_id:current.node_id,display_name:current.display_name,via:'Trail cleared'}];renderTrail();});
    $$('[data-export]').forEach(b=>b.addEventListener('click',()=>exportDossier(b.dataset.export).catch(error=>showToast(`Export failed: ${error.message}`))));
    $$('[data-copy-section]').forEach(b=>b.addEventListener('click',async()=>{await navigator.clipboard.writeText(dossier.features.map(x=>`${x.feature_kind}: ${x.value} (${x.epistemic_kind}; ${x.source})`).join('\n'));showToast('Features copied.');}));
    const dialog=$('#source-dialog');
    $('#source-button').addEventListener('click',()=>dialog.showModal());
    $('#connect-source').addEventListener('click',e=>{const value=$('input[name=source]:checked').value;if(value!=='demo'){e.preventDefault();showToast('Phase 1 only serves the deterministic local fixture API.');}else showToast('Fixture selected.');});
    window.addEventListener('popstate',()=>{const params=new URLSearchParams(location.hash.replace(/^#/, ''));const type=params.get('node_type'), id=params.get('node_id');if(type&&id)navigate(type,id,'history','Browser navigation',false);});
  }

  async function boot() {
    wireEvents();
    try {
      if (FALLBACK) throw new Error('static preview uses demo fallback');
      const session = await json('/api/session');
      apiMode = 'api';
      setSource(`${session.source.label} · ${session.snapshot.snapshot_id}`);
    } catch (error) {
      apiMode = 'fallback';
      setSource('Demo fallback · backend unavailable', false);
      showToast('Using static fixture fallback. Run `uv run jouvence-viewer` for the local API.');
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
