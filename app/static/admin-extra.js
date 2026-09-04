/* Extensions for the Zenith management shell. Loaded after admin.js. */
(function(){
  const style=document.createElement('style');
  style.textContent=`.global-search input{width:260px;border:1px solid var(--line);border-radius:10px;padding:9px 11px;background:#f8fafc;outline:none}.global-search input:focus{border-color:var(--brand);background:#fff}.search-results{position:fixed;right:225px;top:78px;width:min(430px,calc(100vw - 40px));max-height:520px;overflow:auto;background:#fff;border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow);z-index:45;padding:10px}.search-group{padding:8px}.search-group h4{margin:0 0 6px;color:var(--muted);font-size:.72rem;text-transform:uppercase;letter-spacing:.06em}.search-item{display:grid;grid-template-columns:110px 1fr;gap:10px;padding:9px;border-radius:9px;cursor:pointer}.search-item:hover{background:#f3f7f7}.search-item code{color:var(--brand);font-size:.73rem}.search-item strong,.search-item span{display:block}.search-item span{font-size:.76rem;color:var(--muted);margin-top:2px}.audit-payload{max-width:440px;white-space:normal;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.73rem;color:#475467}.branch-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.branch-card{border:1px solid var(--line);border-radius:12px;padding:14px}.branch-card strong,.branch-card span{display:block}.branch-card span{color:var(--muted);font-size:.8rem;margin:4px 0 10px}@media(max-width:900px){.global-search{display:none}.branch-grid{grid-template-columns:1fr}.search-results{right:20px}}`;
  document.head.appendChild(style);

  async function renderService(){
    const [rows,staff]=await Promise.all([api('/tickets?limit=500'),api('/staff')]);
    pageContent.innerHTML=`<div class="panel">${toolbar('Service desk','Customer support requests and human handoffs')}${rowsTable(['Reference','Reason','Queue','Language','Priority','Assigned','Status','Created',''],rows.map(x=>`<tr><td>${esc(x.reference)}</td><td class="wrap">${esc(x.reason)}</td><td>${esc(x.queue)}</td><td>${esc(x.language)}</td><td>${badge(x.priority)}</td><td>${esc(x.assigned_to||'Unassigned')}</td><td>${badge(x.status)}</td><td>${dt(x.created_at)}</td><td class="actions"><button data-ticket="${x.id}">Manage</button></td></tr>`))}</div>`;
    pageContent.querySelectorAll('[data-ticket]').forEach(b=>b.onclick=()=>ticketModal(rows.find(x=>x.id===Number(b.dataset.ticket)),staff));
  }
  function ticketModal(x,staff){
    const fields=[
      {name:'status',label:'Status',type:'select',options:['Open','In Progress','Waiting Customer','Resolved','Closed'].map(v=>({value:v,label:v}))},
      {name:'queue',label:'Queue',type:'select',options:['General support','Policy servicing','Claims','Sales','Payments'].map(v=>({value:v,label:v}))},
      {name:'priority',label:'Priority',type:'select',options:['Low','Normal','High','Urgent'].map(v=>({value:v,label:v}))},
      {name:'assigned_to_id',label:'Assigned staff',type:'select',options:opts(staff,'id','full_name')},
      {name:'notes',label:'Internal notes',type:'textarea',full:true},
    ];
    openModal({title:x.reference,eyebrow:'Service request',fields,initial:x,onSubmit:data=>api(`/tickets/${x.id}`,{method:'PATCH',body:data})});
  }

  async function renderAudit(){
    const rows=await api('/audit?limit=500');
    const draw=data=>rowsTable(['Time','Event','Staff / context','Details'],data.map(x=>`<tr><td>${dt(x.created_at)}</td><td>${esc(x.event_type)}</td><td>${esc(x.payload?.staff_user||x.session_id||'System')}</td><td class="audit-payload">${esc(JSON.stringify(x.payload||{}))}</td></tr>`));
    pageContent.innerHTML=`<div class="panel">${toolbar('Audit trail','Material customer, policy, finance, claims and staff actions','<input id="auditSearch" placeholder="Search audit events...">')}<div id="auditTable">${draw(rows)}</div></div>`;
    document.getElementById('auditSearch').oninput=async e=>{const q=e.target.value.trim();const data=await api(`/audit?limit=500${q?`&q=${encodeURIComponent(q)}`:''}`);document.getElementById('auditTable').innerHTML=draw(data)};
  }

  pages.service=['Service Desk','Customer service',renderService];
  pages.audit=['Audit Trail','Governance',renderAudit];

  const baseLeads=pages.leads[2];
  pages.leads[2]=async function(){
    await baseLeads();
    const toolbarEl=pageContent.querySelector('.panel-head .toolbar');
    if(toolbarEl){const btn=document.createElement('button');btn.className='primary';btn.textContent='+ New lead';btn.onclick=manualLeadModal;toolbarEl.appendChild(btn)}
  };
  async function manualLeadModal(){
    const products=await api('/products?active=true');
    const fields=[
      {name:'name',label:'Customer / prospect name',required:true},
      {name:'mobile',label:'Mobile number',required:true},
      {name:'product',label:'Product',type:'select',options:products.map(x=>({value:x.name,label:x.name})),required:true},
      {name:'status',label:'Stage',type:'select',options:['New','Contacted','Qualified','Quoted'].map(v=>({value:v,label:v})),value:'New'},
      {name:'consent',label:'Contact consent',type:'checkbox',value:true},
    ];
    openModal({title:'New sales lead',eyebrow:'Sales',fields,onSubmit:data=>api('/leads',{method:'POST',body:data})});
  }

  const baseClaims=pages.claims[2];
  pages.claims[2]=async function(){
    await baseClaims();
    const toolbarEl=pageContent.querySelector('.panel-head .toolbar');
    if(toolbarEl){const btn=document.createElement('button');btn.className='primary';btn.textContent='+ Register claim';btn.onclick=manualClaimModal;toolbarEl.appendChild(btn)}
  };
  async function manualClaimModal(){
    const policies=await api('/policies?limit=500');
    const fields=[
      {name:'policy_number',label:'Policy',type:'select',options:policies.map(x=>({value:x.policy_number,label:`${x.policy_number} — ${x.holder_name}`})),required:true},
      {name:'loss_date',label:'Loss date',type:'date',required:true},
      {name:'location',label:'Location',required:true},
      {name:'contact',label:'Contact number',required:true},
      {name:'estimated_damage',label:'Estimated damage',type:'number',step:'0.01'},
      {name:'status',label:'Status',type:'select',options:['Registered','Assessing'].map(v=>({value:v,label:v})),value:'Registered'},
      {name:'description',label:'Incident description',type:'textarea',full:true,required:true},
    ];
    openModal({title:'Register claim',eyebrow:'Claims',fields,onSubmit:data=>api('/claims',{method:'POST',body:data})});
  }

  const baseSettings=pages.settings[2];
  pages.settings[2]=async function(){
    await baseSettings();
    if(state.user?.role!=='Administrator')return;
    const branches=await api('/branches');
    pageContent.insertAdjacentHTML('beforeend',`<div class="panel">${toolbar('Branches','Office locations and operational units','<button id="newBranch" class="primary">+ New branch</button>')}<div class="branch-grid">${branches.map(x=>`<div class="branch-card"><strong>${esc(x.name)}</strong><span>${esc(x.code)} · ${esc(x.location||'No location')}</span>${badge(x.active?'Active':'Inactive')} <button class="secondary" data-branch="${x.id}">Edit</button></div>`).join('')}</div></div><div class="panel">${toolbar('Account security','Change the password for your signed-in staff account','<button id="changePassword" class="secondary">Change password</button>')}</div>`);
    document.getElementById('newBranch').onclick=()=>branchModal();
    pageContent.querySelectorAll('[data-branch]').forEach(b=>b.onclick=()=>branchModal(branches.find(x=>x.id===Number(b.dataset.branch))));
    document.getElementById('changePassword').onclick=passwordModal;
  };
  function branchModal(x=null){
    const fields=x?[{name:'name',label:'Branch name',required:true},{name:'location',label:'Location'},{name:'active',label:'Active',type:'checkbox'}]:[{name:'code',label:'Branch code',required:true},{name:'name',label:'Branch name',required:true},{name:'location',label:'Location'},{name:'active',label:'Active',type:'checkbox',value:true}];
    openModal({title:x?'Edit branch':'New branch',eyebrow:'Administration',fields,initial:x||{},onSubmit:data=>api(x?`/branches/${x.id}`:'/branches',{method:x?'PATCH':'POST',body:data})});
  }
  function passwordModal(){
    const fields=[{name:'current_password',label:'Current password',type:'password',required:true},{name:'new_password',label:'New password',type:'password',required:true}];
    openModal({title:'Change password',eyebrow:'Security',fields,onSubmit:data=>api('/auth/change-password',{method:'POST',body:data})});
  }

  const searchInput=document.getElementById('globalSearch');
  const searchBox=document.getElementById('searchResults');
  let searchTimer;
  if(searchInput){searchInput.addEventListener('input',()=>{clearTimeout(searchTimer);const q=searchInput.value.trim();if(q.length<2){searchBox.classList.add('hidden');return}searchTimer=setTimeout(async()=>{try{const d=await api(`/search?q=${encodeURIComponent(q)}`);const groups=[['Customers',d.customers,'customers'],['Policies',d.policies,'policies'],['Claims',d.claims,'claims'],['Leads',d.leads,'leads']];searchBox.innerHTML=groups.map(([title,items,page])=>items.length?`<div class="search-group"><h4>${title}</h4>${items.map(x=>`<div class="search-item" data-search-page="${page}"><code>${esc(x.reference)}</code><div><strong>${esc(x.label)}</strong><span>${esc(x.detail||'')}</span></div></div>`).join('')}</div>`:'').join('')||empty('No matching records');searchBox.classList.remove('hidden');searchBox.querySelectorAll('[data-search-page]').forEach(i=>i.onclick=()=>{searchBox.classList.add('hidden');searchInput.value='';loadPage(i.dataset.searchPage)})}catch(err){searchBox.innerHTML=empty(err.message);searchBox.classList.remove('hidden')}},250)});document.addEventListener('click',e=>{if(!searchBox.contains(e.target)&&e.target!==searchInput)searchBox.classList.add('hidden')})}
})();
