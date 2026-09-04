/* Maker/checker approvals and document governance UI. */
(function(){
  async function renderApprovals(){
    const [rows,staff]=await Promise.all([api('/core/approvals?limit=500'),api('/staff')]);
    pageContent.innerHTML=`<div class="panel">${toolbar('Approvals & maker/checker','Controlled approvals for underwriting, claims, finance and policy actions','<button id="newApproval" class="primary">+ Request approval</button>')}${rowsTable(['Reference','Workflow','Record','Stage','Amount','Requested by','Assigned','Status',''],rows.map(x=>`<tr><td>${esc(x.reference)}</td><td>${esc(x.workflow)}</td><td>${esc(x.entity_type)} #${esc(x.entity_id)}</td><td>${esc(x.stage)}</td><td>${x.amount==null?'—':money(x.amount)}</td><td>${esc(x.requested_by||'—')}</td><td>${esc(x.assigned_to||'Unassigned')}</td><td>${badge(x.status)}</td><td class="actions">${['Pending','Returned'].includes(x.status)?`<button data-approval="${x.id}">Decide</button>`:''}</td></tr>`))}</div>`;
    el('newApproval').onclick=()=>approvalRequestModal(staff);
    pageContent.querySelectorAll('[data-approval]').forEach(b=>b.onclick=()=>approvalDecisionModal(rows.find(x=>x.id===Number(b.dataset.approval))));
  }
  function approvalRequestModal(staff){
    const fields=[
      {name:'workflow',label:'Workflow',type:'select',options:['Underwriting Referral','Policy Endorsement','Policy Cancellation','Claim Reserve','Claim Settlement','Premium Refund','Credit Note','Compliance Review','Other'].map(v=>({value:v,label:v}))},
      {name:'entity_type',label:'Record type',type:'select',options:['quote','policy','claim','customer','payment','document'].map(v=>({value:v,label:v}))},
      {name:'entity_id',label:'Record ID',type:'number',required:true},
      {name:'stage',label:'Approval stage',value:'Review'},
      {name:'amount',label:'Amount (if applicable)',type:'number',step:'0.01'},
      {name:'assigned_to_id',label:'Assigned approver',type:'select',options:opts(staff,'id','full_name')},
      {name:'reason',label:'Reason / request detail',type:'textarea',full:true},
    ];
    openModal({title:'Request approval',eyebrow:'Maker / checker',fields,onSubmit:data=>api('/core/approvals',{method:'POST',body:data})});
  }
  function approvalDecisionModal(x){
    const fields=[{name:'status',label:'Decision',type:'select',options:['Approved','Rejected','Returned','Cancelled'].map(v=>({value:v,label:v}))},{name:'decision_notes',label:'Decision notes',type:'textarea',full:true}];
    openModal({title:x.reference,eyebrow:`${x.workflow} · ${x.entity_type} #${x.entity_id}`,fields,onSubmit:data=>api(`/core/approvals/${x.id}/decision`,{method:'PATCH',body:data})});
  }

  async function renderDocuments(){
    pageContent.innerHTML=`<div class="panel">${toolbar('Document governance','Classify, version, expire and verify managed documents')}<div class="toolbar" style="margin-bottom:16px"><select id="docEntityType"><option value="customer">Customer</option><option value="policy">Policy</option><option value="claim">Claim</option><option value="lead">Lead</option></select><input id="docEntityId" type="number" placeholder="Record ID"><button id="loadDocs" class="primary">Load documents</button></div><div class="core-note">Upload files from the relevant customer/policy/claim record first, then govern them here with categories, versions, expiry dates and SHA-256 checksums.</div><div id="governedDocs" style="margin-top:16px">${empty('Choose a record to view its documents.')}</div></div>`;
    el('loadDocs').onclick=()=>loadGovernedDocs();
  }
  async function loadGovernedDocs(){
    const type=el('docEntityType').value;const id=Number(el('docEntityId').value);if(!id){toast('Enter a valid record ID');return}
    try{const rows=await api(`/core/documents?entity_type=${encodeURIComponent(type)}&entity_id=${id}`);el('governedDocs').innerHTML=rowsTable(['File','Category','Version','Status','Expiry','Checksum',''],rows.map(x=>`<tr><td>${esc(x.filename)}</td><td>${esc(x.category)}</td><td>v${esc(x.version)}</td><td>${badge(x.document_status)}</td><td>${dte(x.expiry_date)}</td><td class="wrap">${esc(x.checksum_sha256?x.checksum_sha256.slice(0,18)+'…':'Not calculated')}</td><td class="actions"><button data-doc-profile="${x.id}">Govern</button></td></tr>`));el('governedDocs').querySelectorAll('[data-doc-profile]').forEach(b=>b.onclick=()=>documentProfileModal(rows.find(x=>x.id===Number(b.dataset.docProfile))))}catch(err){toast(err.message)}
  }
  function documentProfileModal(x){
    const fields=[{name:'category',label:'Document category',type:'select',options:['KYC','Policy Schedule','Quotation','Claim Evidence','Assessment','Invoice','Receipt','Correspondence','Compliance','General'].map(v=>({value:v,label:v}))},{name:'document_status',label:'Status',type:'select',options:['Current','Superseded','Expired','Rejected','Archived'].map(v=>({value:v,label:v}))},{name:'expiry_date',label:'Expiry date',type:'date'},{name:'supersedes_document_id',label:'Supersedes document ID',type:'number'},{name:'notes',label:'Governance notes',type:'textarea',full:true}];
    openModal({title:x.filename,eyebrow:`Document #${x.id} · v${x.version}`,fields,initial:x,onSubmit:data=>api(`/core/documents/${x.id}/profile`,{method:'PUT',body:data})});
  }

  pages.approvals=['Approvals','Governance',renderApprovals];
  pages.documents=['Document Governance','Governance',renderDocuments];
})();
