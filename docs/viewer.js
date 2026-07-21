(() => {
  'use strict';

  const NODES = {
    BRCA1: {
      id: 'BRCA1', nodeId: 'ENSG00000012048', type: 'gene', name: 'BRCA1', source: 'Ensembl · fixture-v1',
      description: 'DNA repair associated protein 1; a tumor suppressor involved in homologous recombination and genome integrity.',
      ids: { Ensembl: 'ENSG00000012048', HGNC: 'HGNC:1100', NCBI: '672', UniProt: 'P38398' },
      features: [
        ['Biotype', 'protein_coding', 'Ensembl'], ['Text summary', 'DNA repair, homologous recombination and genome integrity.', 'fixture summaries'],
        ['Protein reference', 'BRCA1_HUMAN · P38398', 'UniProt mapping'], ['Genomic context', 'Chromosome 17q21.31', 'Ensembl fixture']
      ],
      connections: [
        ['disease associated gene', [['Breast carcinoma', 'BREAST', 'disease'], ['Lung carcinoma', 'LUNG', 'disease']]],
        ['gene interacts gene', [['TP53', 'TP53', 'gene'], ['EGFR', 'EGFR', 'gene']]],
        ['molecule targets gene', [['Gefitinib', 'GEFITINIB', 'molecule']]]
      ],
      longRange: {
        Diseases: [['Breast carcinoma', 'BREAST', '.94', '2 hops · genetics'], ['Lung carcinoma', 'LUNG', '.72', '2 hops · interaction'], ['Hereditary cancer syndrome', 'BREAST', '.67', '3 hops · phenotype']],
        Genes: [['TP53', 'TP53', '.91', '1 hop · physical'], ['EGFR', 'EGFR', '.78', '2 hops · pathway'], ['BRCA2', 'BRCA2', '.76', '2 hops · repair']],
        Molecules: [['Gefitinib', 'GEFITINIB', '.73', '2 hops · target'], ['Aspirin', 'ASPIRIN', '.52', '3 hops · phenotype']],
        Phenotypes: [['Abnormal cell proliferation', 'PROLIF', '.82', '2 hops · disease'], ['Neoplasm', 'PROLIF', '.68', '3 hops · ontology']]
      },
      putative: [
        ['BRCA1 → lung carcinoma', 'inferred_weak', 'gene_disease_v1', 'BRCA1 → TP53 → lung carcinoma', 'Association path is not a causal disease assertion.'],
        ['gefitinib → breast carcinoma', 'inferred_weak', 'molecule_gene_disease_v1', 'gefitinib → BRCA1 → breast carcinoma', 'Drug action and disease mechanism are incomplete.'],
        ['BRCA1 → abnormal cell proliferation', 'inferred_obvious', 'ontology_context_v1', 'BRCA1 → breast carcinoma → abnormal cell proliferation', 'Ontology-expanded context; not observed gene–phenotype evidence.']
      ],
      evidence: [
        ['disease_associated_gene', 'OpenTargets fixture', 'associated_with', .92, 'fixture:ot:001'],
        ['disease_associated_gene', 'ClinGen fixture', 'germline_role', .88, 'PMID:0000001'],
        ['gene_interacts_gene', 'BioGRID fixture', 'physical_interaction', .81, 'BIOGRID:fixture:12'],
        ['gene_interacts_gene', 'IntAct fixture', 'direct_interaction', .76, 'IMEX:fixture:4'],
        ['molecule_targets_gene', 'ChEMBL fixture', 'binds', .64, 'CHEMBL-ACT:fixture:2']
      ]
    },
    TP53: { id:'TP53',nodeId:'ENSG00000141510',type:'gene',name:'TP53',source:'Ensembl · fixture-v1',description:'Tumor protein p53; a transcription factor coordinating DNA-damage responses, cell-cycle arrest and apoptosis.',ids:{Ensembl:'ENSG00000141510',HGNC:'HGNC:11998',NCBI:'7157',UniProt:'P04637'} },
    EGFR: { id:'EGFR',nodeId:'ENSG00000146648',type:'gene',name:'EGFR',source:'Ensembl · fixture-v1',description:'Epidermal growth factor receptor; a receptor tyrosine kinase involved in proliferation and survival signaling.',ids:{Ensembl:'ENSG00000146648',HGNC:'HGNC:3236',NCBI:'1956',UniProt:'P00533'} },
    BRCA2: { id:'BRCA2',nodeId:'ENSG00000139618',type:'gene',name:'BRCA2',source:'Ensembl · fixture-v1',description:'DNA repair associated protein 2; a mediator of homologous recombination.',ids:{Ensembl:'ENSG00000139618',HGNC:'HGNC:1101',NCBI:'675',UniProt:'P51587'} },
    BREAST: { id:'BREAST',nodeId:'EFO:0000305',type:'disease',name:'Breast carcinoma',source:'OpenTargets · fixture-v1',description:'A malignant neoplasm arising from breast tissue.',ids:{EFO:'EFO:0000305',MONDO:'MONDO:0007254',MeSH:'D001943',ICD10:'C50'} },
    LUNG: { id:'LUNG',nodeId:'EFO:0000616',type:'disease',name:'Lung carcinoma',source:'OpenTargets · fixture-v1',description:'A malignant neoplasm originating in lung tissue.',ids:{EFO:'EFO:0000616',MONDO:'MONDO:0004992',MeSH:'D008545'} },
    GEFITINIB: { id:'GEFITINIB',nodeId:'CHEMBL1201585',type:'molecule',name:'Gefitinib',source:'ChEMBL · fixture-v1',description:'A small-molecule EGFR tyrosine kinase inhibitor.',ids:{ChEML:'CHEMBL1201585',DrugBank:'DB00317',PubChem:'123631'} },
    ASPIRIN: { id:'ASPIRIN',nodeId:'CHEMBL25',type:'molecule',name:'Aspirin',source:'ChEMBL · fixture-v1',description:'Acetylsalicylic acid; a cyclooxygenase inhibitor.',ids:{ChEML:'CHEMBL25',DrugBank:'DB00945',PubChem:'2244'} },
    PROLIF: { id:'PROLIF',nodeId:'HP:0003011',type:'phenotype',name:'Abnormal cell proliferation',source:'HPO · fixture-v1',description:'A phenotype involving altered regulation or rate of cellular proliferation.',ids:{HPO:'HP:0003011'} }
  };

  const TYPE_LABEL = {gene:'GN',disease:'DS',molecule:'MO',phenotype:'PH'};
  const DEFAULT_FEATURES = node => [
    ['Canonical type', node.type, node.source.split(' · ')[0]],
    ['Text summary', node.description, 'fixture summaries'],
    ['Identifier coverage', `${Object.keys(node.ids).length} linked namespaces`, 'node registry'],
    ['Snapshot', 'fixture-v1', 'viewer manifest']
  ];
  const genericConnections = node => {
    if (node.type === 'gene') return [['gene interacts gene', [['BRCA1','BRCA1','gene'],['TP53','TP53','gene'],['EGFR','EGFR','gene']].filter(x=>x[1]!==node.id)],['disease associated gene',[['Breast carcinoma','BREAST','disease'],['Lung carcinoma','LUNG','disease']]]];
    if (node.type === 'disease') return [['disease associated gene',[['BRCA1','BRCA1','gene'],['TP53','TP53','gene'],['EGFR','EGFR','gene']]],['disease has phenotype',[['Abnormal cell proliferation','PROLIF','phenotype']]]];
    if (node.type === 'molecule') return [['molecule targets gene',[['EGFR','EGFR','gene'],['TP53','TP53','gene']]],['molecule treats disease',[['Lung carcinoma','LUNG','disease']]]];
    return [['disease has phenotype',[['Breast carcinoma','BREAST','disease'],['Lung carcinoma','LUNG','disease']]],['gene associated phenotype',[['TP53','TP53','gene']]]];
  };
  const genericLong = () => ({Diseases:[['Breast carcinoma','BREAST','.82','2 hops · evidence'],['Lung carcinoma','LUNG','.74','2 hops · context']],Genes:[['BRCA1','BRCA1','.79','2 hops · graph'],['TP53','TP53','.76','2 hops · graph'],['EGFR','EGFR','.69','3 hops · graph']],Molecules:[['Gefitinib','GEFITINIB','.71','2 hops · target'],['Aspirin','ASPIRIN','.48','3 hops · context']],Phenotypes:[['Abnormal cell proliferation','PROLIF','.77','2 hops · ontology']]});
  const genericPutative = node => [[`${node.name} → ${node.type==='disease'?'gefitinib':'breast carcinoma'}`,'inferred_weak','fixture_path_v1',`${node.name} → TP53 → candidate`,'Fixture hypothesis; mechanism and sign require review.']];
  const genericEvidence = node => [['fixture_relation','OpenTargets fixture','associated_with',.78,`fixture:${node.id}:1`],['fixture_relation','BioGRID fixture','supports',.66,`fixture:${node.id}:2`]];
  Object.values(NODES).forEach(node => {
    node.features ||= DEFAULT_FEATURES(node);
    node.connections ||= genericConnections(node);
    node.longRange ||= genericLong();
    node.putative ||= genericPutative(node);
    node.evidence ||= genericEvidence(node);
  });

  const $ = selector => document.querySelector(selector);
  const $$ = selector => [...document.querySelectorAll(selector)];
  let current = NODES.BRCA1;
  let trail = [{id:'BRCA1', via:'Search start'}];
  let toastTimer;

  function esc(value) { return String(value).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
  function nodeLink(label,id,type,via) {
    return `<a class="node-link js-node-link" href="#node=${encodeURIComponent(id)}" data-node="${esc(id)}" data-via="${esc(via)}"><span class="node-glyph">${TYPE_LABEL[type]||'ND'}</span><span><strong>${esc(label)}</strong><small>${esc(NODES[id]?.nodeId||id)}</small></span><b>→</b></a>`;
  }
  function miniLink(label,id,meta,via) { return `<a class="js-node-link" href="#node=${encodeURIComponent(id)}" data-node="${esc(id)}" data-via="${esc(via)}">${esc(label)}</a><small>${esc(NODES[id]?.nodeId||id)} · ${esc(meta)}</small>`; }

  function render(node) {
    current = node;
    $('#entity-type').textContent = node.type.toUpperCase();
    $('#entity-source').textContent = node.source;
    $('#entity-name').textContent = node.name;
    $('#entity-description').textContent = node.description;
    $('#entity-ids').innerHTML = Object.entries(node.ids).map(([k,v]) => `<span><b>${esc(k)}</b> ${esc(v)}</span>`).join('');
    const directCount = node.connections.reduce((n,g)=>n+g[1].length,0);
    $('#stat-direct').textContent = directCount;
    $('#stat-evidence').textContent = node.evidence.length;
    $('#stat-putative').textContent = node.putative.length;
    $('#feature-grid').innerHTML = node.features.map(([k,v,s])=>`<article class="feature-card"><span>${esc(k).toUpperCase()}</span><h3>${esc(v)}</h3><p>Source-backed node feature. Coverage and meaning remain source-dependent.</p><footer>${esc(s)}</footer></article>`).join('');
    $('#connections-list').innerHTML = node.connections.map(([relation,items])=>`<section class="connection-group"><header><h3>${esc(relation.replaceAll('_',' '))}</h3><span>${items.length} observed</span></header><div class="node-links">${items.map(([label,id,type])=>nodeLink(label,id,type,relation)).join('')}</div></section>`).join('');
    $('#long-range-grid').innerHTML = Object.entries(node.longRange).map(([family,items])=>`<article class="long-card"><header><h3>${esc(family)}</h3><span>TOP ${Math.min(5,items.length)}</span></header>${items.map(([label,id,score,meta],i)=>`<div class="rank-row"><span>${i+1}</span><div>${miniLink(label,id,meta,'ranked '+family.toLowerCase())}</div><b class="rank-score">${esc(score)}</b></div>`).join('')}</article>`).join('');
    $('#putative-list').innerHTML = node.putative.map(([label,confidence,template,path,caveat])=>`<details class="putative-row"><summary><span class="hypothesis-badge">HYPOTHESIS</span><span><strong>${esc(label)}</strong><small>${esc(confidence)} · not observed</small></span><b>+</b></summary><div class="putative-detail"><div><span>TEMPLATE</span><p>${esc(template)}</p></div><div><span>SUPPORT PATH</span><p>${esc(path)}</p></div><div><span>CAVEAT</span><p>${esc(caveat)}</p></div></div></details>`).join('');
    const relations=[...new Set(node.evidence.map(e=>e[0]))];
    $('#evidence-filter').innerHTML='<option value="all">All relations</option>'+relations.map(r=>`<option value="${esc(r)}">${esc(r.replaceAll('_',' '))}</option>`).join('');
    renderEvidence('all');
    renderTrail();
    document.title=`${node.name} — Jouvence-Graph viewer preview`;
    bindNodeLinks();
  }

  function renderEvidence(filter) {
    $('#evidence-body').innerHTML=current.evidence.filter(e=>filter==='all'||e[0]===filter).map(([r,s,p,score,ref])=>`<tr><td><code>${esc(r)}</code></td><td>${esc(s)}</td><td>${esc(p)}</td><td>${Number(score).toFixed(2)}</td><td><a href="#reference-${encodeURIComponent(ref)}">${esc(ref)}</a></td></tr>`).join('');
  }
  function renderTrail() {
    $('#history-list').innerHTML=trail.map((step,i)=>{const n=NODES[step.id];return `<li class="history-step ${i===trail.length-1?'current':''}" data-history-index="${i}"><span>${esc(step.via)}</span><strong>${esc(n.name)}</strong><small>${esc(n.nodeId)}</small></li>`}).join('');
    $('#history-count').textContent=`${trail.length} node${trail.length===1?'':'s'}`;
    $$('.history-step').forEach(el=>el.addEventListener('click',()=>{const i=Number(el.dataset.historyIndex);trail=trail.slice(0,i+1);render(NODES[trail[i].id]);history.pushState({node:trail[i].id},'',`#node=${encodeURIComponent(trail[i].id)}`)}));
  }
  function navigate(id,mode='link',via='linked node') {
    const node=NODES[id]; if(!node)return;
    if(mode==='search') trail=[{id,via:'Search start'}];
    else if(trail.at(-1)?.id!==id) trail.push({id,via});
    render(node); history.pushState({node:id},'',`#node=${encodeURIComponent(id)}`); window.scrollTo({top:0,behavior:'smooth'});
  }
  function bindNodeLinks() { $$('.js-node-link').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();navigate(a.dataset.node,'link',a.dataset.via)})); }

  function search(query) {
    const q=query.trim().toLowerCase();
    const results=q?Object.values(NODES).filter(n=>[n.name,n.nodeId,...Object.values(n.ids)].some(v=>String(v).toLowerCase().includes(q))).slice(0,12):[];
    const box=$('#search-results');
    box.innerHTML=results.map(n=>`<button class="search-result" role="option" data-search-node="${esc(n.id)}"><span class="mini-type">${esc(n.type.toUpperCase())}</span><span><strong>${esc(n.name)}</strong><small>${esc(n.description)}</small></span><code>${esc(n.nodeId)}</code></button>`).join('') || (q?'<div class="search-result"><span></span><span><strong>No fixture match</strong><small>The production index will cover every canonical node type and reference ID.</small></span></div>':'');
    box.hidden=!q; $('#global-search').setAttribute('aria-expanded',String(!!q));
    $$('[data-search-node]').forEach(b=>b.addEventListener('click',()=>{navigate(b.dataset.searchNode,'search');box.hidden=true;$('#global-search').value=''}));
  }

  function dossierMarkdown() {
    const lines=[`---`,`node_id: ${current.nodeId}`,`node_type: ${current.type}`,`snapshot_id: fixture-v1`,`exported_from: Jouvence-Graph viewer proposal`,`---`,``,`# ${current.name}`,``,current.description,``,`## Identifiers`,...Object.entries(current.ids).map(([k,v])=>`- **${k}:** ${v}`),``,`## Features`,...current.features.map(([k,v,s])=>`- **${k}:** ${v} — ${s}`),``,`## Direct connections`];
    current.connections.forEach(([r,items])=>{lines.push(`### ${r}`,...items.map(([label,id])=>`- ${label} (${NODES[id]?.nodeId||id})`))});
    lines.push('','## Putative links','> Hypotheses below are graph-derived and not observed assertions.',...current.putative.map(p=>`- **${p[0]}** — ${p[1]}; template: ${p[2]}; path: ${p[3]}`),'','## Navigation trail',...trail.map((s,i)=>`${i+1}. ${NODES[s.id].name} (${NODES[s.id].nodeId}) — ${s.via}`)); return lines.join('\n');
  }
  function dossierCsv() {
    const rows=[['section','row_type','node_id','label','value','source_or_via']];
    Object.entries(current.ids).forEach(([k,v])=>rows.push(['node','identifier',current.nodeId,k,v,'fixture-v1']));
    current.features.forEach(([k,v,s])=>rows.push(['features','feature',current.nodeId,k,v,s]));
    current.connections.forEach(([r,items])=>items.forEach(([label,id])=>rows.push(['edges','observed',current.nodeId,r,NODES[id]?.nodeId||id,label])));
    current.putative.forEach(p=>rows.push(['putative','inferred',current.nodeId,p[2],p[0],p[1]]));
    trail.forEach((s,i)=>rows.push(['history',String(i+1),NODES[s.id].nodeId,NODES[s.id].name,s.via,'session']));
    return rows.map(r=>r.map(v=>`"${String(v).replaceAll('"','""')}"`).join(',')).join('\n');
  }
  function download(name,content,type) { const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([content],{type}));a.download=name;document.body.append(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove()},0); }
  function showToast(text){clearTimeout(toastTimer);const t=$('#toast');t.textContent=text;t.classList.add('show');toastTimer=setTimeout(()=>t.classList.remove('show'),2400)}

  $('#global-search').addEventListener('input',e=>search(e.target.value));
  $('#global-search').addEventListener('keydown',e=>{if(e.key==='Escape'){$('#search-results').hidden=true;e.target.blur()}if(e.key==='Enter'){const first=$('[data-search-node]');if(first)first.click()}});
  document.addEventListener('keydown',e=>{if(e.key==='/'&&document.activeElement.tagName!=='INPUT'){e.preventDefault();$('#global-search').focus()}});
  document.addEventListener('click',e=>{if(!e.target.closest('.viewer-search-wrap'))$('#search-results').hidden=true});
  $('#evidence-filter').addEventListener('change',e=>renderEvidence(e.target.value));
  $('#clear-history').addEventListener('click',()=>{trail=[{id:current.id,via:'Trail cleared'}];renderTrail()});
  $$('[data-export]').forEach(b=>b.addEventListener('click',()=>{const kind=b.dataset.export,slug=current.name.toLowerCase().replace(/\W+/g,'-');if(kind==='markdown')download(`${slug}-dossier.md`,dossierMarkdown(),'text/markdown');else if(kind==='csv')download(`${slug}-dossier-and-history.csv`,dossierCsv(),'text/csv');else window.print();showToast(kind==='pdf'?'Print dialog opened — choose Save as PDF.':`${kind.toUpperCase()} export created.`)}));
  $$('[data-copy-section]').forEach(b=>b.addEventListener('click',async()=>{await navigator.clipboard.writeText(current.features.map(x=>`${x[0]}: ${x[1]} (${x[2]})`).join('\n'));showToast('Features copied.')}));

  const dialog=$('#source-dialog');
  $('#source-button').addEventListener('click',()=>dialog.showModal());
  $$('input[name=source]').forEach(r=>r.addEventListener('change',()=>{
    $$('.source-option').forEach(o=>o.classList.toggle('selected',o.contains(r)&&r.checked));
    $('#local-path').disabled=r.value!=='local';$('#billing-project').disabled=r.value!=='gcs';
    $('#connect-source').textContent=r.value==='demo'?'Use demo fixture':'Backend required';
    $('#source-message').textContent=r.value==='demo'?'The deterministic fixture is ready.':r.value==='local'?'The production localhost backend will validate this root and offer to build a query bundle.':'The production backend will use host ADC plus this consumer billing project; no credentials enter the browser.';
  }));
  $('#connect-source').addEventListener('click',e=>{const value=$('input[name=source]:checked').value;if(value!=='demo'){e.preventDefault();showToast('This preview is fixture-only. The real connection is specified in the proposal.')}else showToast('Demo fixture connected.')});
  window.addEventListener('popstate',()=>{const id=new URLSearchParams(location.hash.replace(/^#/, '')).get('node');if(id&&NODES[id])render(NODES[id])});

  const initial=new URLSearchParams(location.hash.replace(/^#/, '')).get('node');
  if(initial&&NODES[initial])trail=[{id:initial,via:'Direct URL'}];
  render(NODES[initial]||current);
})();
