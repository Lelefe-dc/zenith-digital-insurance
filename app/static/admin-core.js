/* Core insurance extensions: underwriting, lifecycle, customer 360, compliance and executive reporting. */
(function(){
  const coreStyle=document.createElement('style');
  coreStyle.textContent=`
    .core-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
    .core-metric{background:#fff;border:1px solid var(--line);border-radius:16px;padding:18px;box-shadow:var(--shadow-sm)}
    .core-metric span{display:block;color:var(--muted);font-size:.72rem;font-weight:700}.core-metric strong{display:block;font-size:1.55rem;margin-top:8px;letter-spacing:-.03em}.core-metric small{display:block;color:#91a09c;font-size:.66rem;margin-top:6px}
    .detail-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.detail-card{border:1px solid var(--line);border-radius:13px;padding:14px;background:#fbfcfc}.detail-card span,.detail-card strong{display:block}.detail-card span{color:var(--muted);font-size:.68rem}.detail-card strong{margin-top:5px;font-size:.9rem}.core-note{padding:12px 14px;border-radius:12px;background:var(--gold-soft);color:#6d5714;font-size:.75rem;line-height:1.5;border:1px solid #efe2aa}.core-actions{display:flex;gap:6px;flex-wrap:wrap}.core-actions button,.core-actions a{border:1px solid #dce6e3;background:#f6faf9;color:var(--brand-dark);border-radius:8px;padding:6px 9px;cursor:pointer;font-size:.69rem;font-weight:750;text-decoration:none}.core-actions button:hover{background:#eaf5f2}.section-stack{display:grid;gap:14px}.section-stack h3{margin:0 0 8px;font-size:.9rem}.mini-list{display:grid;gap:7px}.mini-row{display:flex;justify-content:space-between;gap:12px;border-bottom:1px solid var(--line);padding:8px 0;font-size:.75rem}.mini-row:last-child{border-bottom:0}.mini-row span{color:var(--muted)}
    @media(max-width:900px){.core-metrics,.detail-grid{grid-template-columns:1fr 1fr}}@media(max-width:620px){.core-metrics,.detail-grid{grid-template-columns:1fr}}
  `;
  document.head.appendChild(coreStyle);

  function fmtPct(v){return `${Number(v||0).toFixed(1)}%`}
  async function downloadPdf(path,filename){
    const r=await fetch(`/api/v1/management${path}`,{headers:{Authorization:`Bearer ${state.token}`}});
    if(!r.ok){let msg='Download failed';try{const d=await r.json();msg=d.detail||msg}catch{}throw new Error(msg)}
    const blob=await r.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=filename||'document.pdf';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),2000);
  }

  async function renderUnderwriting(){
    const [quotes,lookups]=await Promise.all([api('/core/quotes?limit=500'),loadLookups()]);
    pageContent.innerHTML=`<div class="panel">${toolbar('Underwriting & quotations','Rate, refer, approve and convert quotations','<input id="quoteSearch" placeholder="Search quotations..."><button id="newCoreQuote" class="primary">+ Rate quotation</button>')}<div class="core-note">The rating engine is configurable. Current default factors are operational placeholders until Zenith-approved tariff tables and tax/levy rules are loaded.</div><div style="height:12px"></div>${quoteTable(quotes)}</div>`;
    el('newCoreQuote').onclick=()=>rateQuoteModal(lookups);
    el('quoteSearch').oninput=async e=>{const rows=await api(`/core/quotes?limit=500&q=${encodeURIComponent(e.target.value)}`);const old=pageContent.querySelector('.table-wrap');if(old)old.outerHTML=quoteTable(rows)};
    wireQuoteButtons(quotes,lookups);
  }
  function quoteTable(rows){return rowsTable(['Quote','Customer','Product','Sum insured','Premium','Status','Valid until',''],rows.map(x=>`<tr><td>${esc(x.reference)}</td><td>${esc(x.customer_name||'Unlinked')}</td><td>${esc(x.product||'—')}</td><td>${money(x.sum_insured)}</td><td>${money(x.total_premium)}</td><td>${badge(x.status)}</td><td>${dte(x.valid_until)}</td><td><div class="core-actions"><button data-quote-manage="${x.id}">Decision</button><button data-quote-pdf="${x.id}">PDF</button>${x.status==='Approved'?`<button data-quote-convert="${x.id}">Convert</button>`:''}</div></td></tr>`))}
  function wireQuoteButtons(rows,lookups){
    pageContent.querySelectorAll('[data-quote-manage]').forEach(b=>b.onclick=()=>quoteDecisionModal(rows.find(x=>x.id===Number(b.dataset.quoteManage)),lookups));
    pageContent.querySelectorAll('[data-quote-pdf]').forEach(b=>b.onclick=async()=>{const x=rows.find(r=>r.id===Number(b.dataset.quotePdf));try{await downloadPdf(`/core/quotes/${x.id}/pdf`,`${x.reference}.pdf`)}catch(err){toast(err.message)}});
    pageContent.querySelectorAll('[data-quote-convert]').forEach(b=>b.onclick=()=>quoteConvertModal(rows.find(x=>x.id===Number(b.dataset.quoteConvert)),lookups));
  }
  function rateQuoteModal(lookups){
    const fields=[
      {name:'customer_id',label:'Customer',type:'select',options:opts(lookups.customers,'id','full_name')},
      {name:'product_id',label:'Product',type:'select',options:opts(lookups.products,'id','name'),required:true},
      {name:'sum_insured',label:'Sum insured',type:'number',step:'0.01',required:true},
      {name:'excess_amount',label:'Excess',type:'number',step:'0.01',value:0},
      {name:'usage',label:'Risk usage / purpose'},
      {name:'claims_count',label:'Prior claims count',type:'number',value:0},
      {name:'driver_age',label:'Driver age (motor)',type:'number'},
      {name:'vehicle_age',label:'Vehicle age (motor)',type:'number'},
      {name:'security_features',label:'Security features',type:'checkbox',value:false},
      {name:'no_claim_bonus',label:'No-claim bonus eligible',type:'checkbox',value:false},
    ];
    openModal({title:'Rate quotation',eyebrow:'Underwriting engine',fields,onSubmit:data=>{
      const risk={usage:data.usage,claims_count:data.claims_count||0,driver_age:data.driver_age,vehicle_age:data.vehicle_age,security_features:data.security_features,no_claim_bonus:data.no_claim_bonus};
      return api('/core/quotes/rate',{method:'POST',body:{customer_id:data.customer_id,product_id:data.product_id,sum_insured:data.sum_insured,excess_amount:data.excess_amount||0,risk}})
    }});
  }
  function quoteDecisionModal(x,lookups){
    const fields=[{name:'status',label:'Decision',type:'select',options:['Quoted','Referred','Approved','Declined'].map(v=>({value:v,label:v}))},{name:'underwriter_id',label:'Underwriter',type:'select',options:opts(lookups.staff,'id','full_name')},{name:'decision_notes',label:'Decision notes',type:'textarea',full:true}];
    openModal({title:x.reference,eyebrow:'Underwriting decision',fields,initial:x,onSubmit:data=>api(`/core/quotes/${x.id}/decision`,{method:'PATCH',body:data})});
  }
  function quoteConvertModal(x,lookups){
    const fields=[{name:'effective_date',label:'Effective date',type:'date',required:true},{name:'expiry_date',label:'Expiry date',type:'date'},{name:'payment_frequency',label:'Payment frequency',type:'select',options:['Monthly','Quarterly','Annually','Once-off'].map(v=>({value:v,label:v})),value:'Monthly'},{name:'branch_id',label:'Branch',type:'select',options:opts(lookups.branches)},{name:'agent_id',label:'Agent',type:'select',options:opts(lookups.staff,'id','full_name')},{name:'risk_address',label:'Risk address',full:true}];
    openModal({title:`Convert ${x.reference}`,eyebrow:'Policy issuance',fields,onSubmit:data=>api(`/core/quotes/${x.id}/convert`,{method:'POST',body:data})});
  }

  async function renderLifecycle(){
    const [policies,intermediaries]=await Promise.all([api('/policies?limit=500'),api('/core/intermediaries?active=true')]);
    pageContent.innerHTML=`<div class="panel">${toolbar('Policy lifecycle','Endorsements, renewals, suspensions, cancellations and reinstatements')}${rowsTable(['Policy','Holder','Product','Premium','Expiry','Status',''],policies.map(x=>`<tr><td>${esc(x.policy_number)}</td><td>${esc(x.holder_name)}</td><td>${esc(x.product)}</td><td>${money(x.premium,x.currency)}</td><td>${dte(x.expiry_date)}</td><td>${badge(x.status)}</td><td><div class="core-actions"><button data-life-action="${x.id}">Action</button><button data-life-history="${x.id}">History</button><button data-life-pdf="${x.id}">Schedule</button><button data-life-agent="${x.id}">Intermediary</button></div></td></tr>`))}</div>`;
    pageContent.querySelectorAll('[data-life-action]').forEach(b=>b.onclick=()=>lifecycleModal(policies.find(x=>x.id===Number(b.dataset.lifeAction))));
    pageContent.querySelectorAll('[data-life-history]').forEach(b=>b.onclick=()=>showPolicyHistory(policies.find(x=>x.id===Number(b.dataset.lifeHistory))));
    pageContent.querySelectorAll('[data-life-pdf]').forEach(b=>b.onclick=async()=>{const x=policies.find(r=>r.id===Number(b.dataset.lifePdf));try{await downloadPdf(`/core/policies/${x.id}/schedule.pdf`,`${x.policy_number}-schedule.pdf`)}catch(err){toast(err.message)}});
    pageContent.querySelectorAll('[data-life-agent]').forEach(b=>b.onclick=()=>intermediaryAssignModal(policies.find(x=>x.id===Number(b.dataset.lifeAgent)),intermediaries));
  }
  function lifecycleModal(x){
    const fields=[{name:'action',label:'Lifecycle action',type:'select',options:['Endorse','Renew','Suspend','Cancel','Reinstate','Expire'].map(v=>({value:v,label:v}))},{name:'effective_date',label:'Effective date',type:'date',required:true},{name:'premium',label:'New premium (optional)',type:'number',step:'0.01'},{name:'sum_insured',label:'New sum insured (optional)',type:'number',step:'0.01'},{name:'expiry_date',label:'New expiry date (optional)',type:'date'},{name:'reason',label:'Reason / endorsement detail',type:'textarea',full:true}];
    openModal({title:x.policy_number,eyebrow:'Policy lifecycle',fields,onSubmit:data=>api(`/core/policies/${x.id}/action`,{method:'POST',body:data})});
  }
  async function showPolicyHistory(x){
    try{const rows=await api(`/core/policies/${x.id}/history`);openModal({title:`${x.policy_number} history`,eyebrow:'Policy transactions',fields:[],submit:'Close',onSubmit:async()=>{}});modalForm.innerHTML=`<div class="full">${rowsTable(['Action','Effective','From','To','Premium after','Created by'],rows.map(r=>`<tr><td>${esc(r.transaction_type)}</td><td>${dte(r.effective_date)}</td><td>${esc(r.previous_status||'—')}</td><td>${esc(r.new_status||'—')}</td><td>${r.premium_after==null?'—':money(r.premium_after)}</td><td>${esc(r.created_by||'System')}</td></tr>`))}</div><div class="modal-actions"><button type="button" class="primary" data-close-modal>Close</button></div>`}catch(err){toast(err.message)}
  }
  function intermediaryAssignModal(x,rows){
    const fields=[{name:'intermediary_id',label:'Intermediary',type:'select',options:opts(rows,'id','name'),required:true},{name:'commission_rate',label:'Commission rate % (optional override)',type:'number',step:'0.01'}];
    openModal({title:x.policy_number,eyebrow:'Intermediary assignment',fields,onSubmit:data=>api(`/core/policies/${x.id}/intermediary`,{method:'PUT',body:data})});
  }

  async function renderCustomer360(){
    const customers=await api('/customers?limit=500');
    pageContent.innerHTML=`<div class="panel">${toolbar('Customer 360','A complete operational view of policy, premium, claims, KYC and service history','<input id="c360Search" placeholder="Search customer..."><button id="c360Open" class="primary">Open selected customer</button>')}<label style="display:block;max-width:520px"><select id="c360Select" style="width:100%;padding:12px;border:1px solid var(--line);border-radius:11px">${opts(customers,'id','full_name','Select a customer...').map(o=>`<option value="${esc(o.value)}">${esc(o.label)}</option>`).join('')}</select></label><div id="c360Body" style="margin-top:18px">${empty('Select a customer to open the 360° profile.')}</div></div>`;
    el('c360Open').onclick=()=>{const id=Number(el('c360Select').value);if(id)drawCustomer360(id)};
    el('c360Search').oninput=e=>{const q=e.target.value.toLowerCase();const filtered=customers.filter(x=>`${x.full_name} ${x.customer_number} ${x.mobile}`.toLowerCase().includes(q));el('c360Select').innerHTML=opts(filtered,'id','full_name','Select a customer...').map(o=>`<option value="${esc(o.value)}">${esc(o.label)}</option>`).join('')};
  }
  async function drawCustomer360(id){
    try{const d=await api(`/core/customers/${id}/360`);const c=d.customer;const k=d.kyc;el('c360Body').innerHTML=`<div class="section-stack"><div class="detail-grid"><div class="detail-card"><span>Customer</span><strong>${esc(c.full_name)}</strong><small>${esc(c.customer_number)}</small></div><div class="detail-card"><span>KYC</span><strong>${esc(k?.verification_status||'Not started')}</strong><small>${esc(k?.risk_rating||'No risk rating')}</small></div><div class="detail-card"><span>Outstanding premium</span><strong>${money(d.summary.premium_outstanding)}</strong><small>${d.summary.policy_count} policies · ${d.summary.claim_count} claims</small></div></div><div class="core-actions"><button id="c360Kyc">Review KYC</button></div><div class="two-col"><div class="panel">${toolbar('Policies','Current and historic cover')}${rowsTable(['Policy','Product','Status','Premium'],d.policies.map(p=>`<tr><td>${esc(p.policy_number)}</td><td>${esc(p.product)}</td><td>${badge(p.status)}</td><td>${money(p.premium,p.currency)}</td></tr>`))}</div><div class="panel">${toolbar('Claims','Claims linked to customer policies')}${rowsTable(['Claim','Policy','Loss','Status'],d.claims.map(x=>`<tr><td>${esc(x.reference)}</td><td>${esc(x.policy_number)}</td><td>${dte(x.loss_date)}</td><td>${badge(x.status)}</td></tr>`))}</div></div><div class="two-col"><div class="panel">${toolbar('Quotations','Underwriting history')}${rowsTable(['Quote','Product','Premium','Status'],d.quotes.map(x=>`<tr><td>${esc(x.reference)}</td><td>${esc(x.product)}</td><td>${money(x.total_premium)}</td><td>${badge(x.status)}</td></tr>`))}</div><div class="panel">${toolbar('Premium ledger','Billing and receipts')}${rowsTable(['Ref','Policy','Amount','Paid','Status'],d.payments.map(x=>`<tr><td>${esc(x.reference)}</td><td>${esc(x.policy_number||'—')}</td><td>${money(x.amount,x.currency)}</td><td>${money(x.paid_amount,x.currency)}</td><td>${badge(x.status)}</td></tr>`))}</div></div></div>`;el('c360Kyc').onclick=()=>kycModal(c,k)}catch(err){toast(err.message)}
  }
  function kycModal(customer,kyc){
    const fields=[{name:'verification_status',label:'Verification status',type:'select',options:['Pending','In Review','Verified','Rejected'].map(v=>({value:v,label:v}))},{name:'identity_type',label:'Identity type'},{name:'identity_number',label:'Identity number'},{name:'proof_of_address_status',label:'Proof of address',type:'select',options:['Pending','Verified','Rejected'].map(v=>({value:v,label:v}))},{name:'pep_status',label:'PEP assessment',type:'select',options:['Not Assessed','Clear','Potential Match','Confirmed'].map(v=>({value:v,label:v}))},{name:'sanctions_status',label:'Sanctions assessment',type:'select',options:['Not Assessed','Clear','Potential Match','Confirmed'].map(v=>({value:v,label:v}))},{name:'risk_rating',label:'Risk rating',type:'select',options:['Low','Normal','High'].map(v=>({value:v,label:v}))},{name:'notes',label:'Compliance notes',type:'textarea',full:true}];
    openModal({title:`KYC · ${customer.full_name}`,eyebrow:customer.customer_number,fields,initial:kyc||{},onSubmit:data=>api(`/core/customers/${customer.id}/kyc`,{method:'PUT',body:data})});
  }

  async function renderIntermediaries(){
    const rows=await api('/core/intermediaries');
    pageContent.innerHTML=`<div class="panel">${toolbar('Agents & brokers','Intermediary registry and commission rates','<button id="newIntermediary" class="primary">+ New intermediary</button>')}${rowsTable(['Code','Name','Type','Email','Mobile','Commission','Status',''],rows.map(x=>`<tr><td>${esc(x.code)}</td><td>${esc(x.name)}</td><td>${esc(x.intermediary_type)}</td><td>${esc(x.email||'—')}</td><td>${esc(x.mobile||'—')}</td><td>${fmtPct(x.commission_rate)}</td><td>${badge(x.active?'Active':'Inactive')}</td><td class="actions"><button data-intermediary="${x.id}">Edit</button></td></tr>`))}</div>`;
    el('newIntermediary').onclick=()=>intermediaryModal();pageContent.querySelectorAll('[data-intermediary]').forEach(b=>b.onclick=()=>intermediaryModal(rows.find(x=>x.id===Number(b.dataset.intermediary))));
  }
  function intermediaryModal(x=null){
    const fields=x?[{name:'name',label:'Name',required:true},{name:'intermediary_type',label:'Type',type:'select',options:['Agent','Broker','Agency'].map(v=>({value:v,label:v}))},{name:'email',label:'Email',type:'email'},{name:'mobile',label:'Mobile'},{name:'commission_rate',label:'Commission rate %',type:'number',step:'0.01'},{name:'active',label:'Active',type:'checkbox'}]:[{name:'code',label:'Code',required:true},{name:'name',label:'Name',required:true},{name:'intermediary_type',label:'Type',type:'select',options:['Agent','Broker','Agency'].map(v=>({value:v,label:v})),value:'Agent'},{name:'email',label:'Email',type:'email'},{name:'mobile',label:'Mobile'},{name:'commission_rate',label:'Commission rate %',type:'number',step:'0.01',value:0},{name:'active',label:'Active',type:'checkbox',value:true}];
    openModal({title:x?'Edit intermediary':'New intermediary',eyebrow:'Distribution',fields,initial:x||{},onSubmit:data=>api(x?`/core/intermediaries/${x.id}`:'/core/intermediaries',{method:x?'PATCH':'POST',body:data})});
  }

  async function renderExecutive(){
    const d=await api('/core/reports/executive');
    const metrics=[['Written premium',money(d.written_premium)],['Premium collected',money(d.premium_collected)],['Outstanding premium',money(d.premium_outstanding)],['Claims paid',money(d.claims_paid)],['Claims reserve',money(d.claims_reserve)],['Loss ratio',fmtPct(d.loss_ratio_pct)],['Active policies',Number(d.active_policies).toLocaleString()],['Open claims',Number(d.open_claims).toLocaleString()],['Renewals',Number(d.renewals).toLocaleString()],['Cancellations',Number(d.cancellations).toLocaleString()],['Quotations',Number(d.quotes).toLocaleString()],['Quote conversion',fmtPct(d.quote_conversion_pct)]];
    pageContent.innerHTML=`<div class="panel">${toolbar('Executive insurance dashboard','Portfolio, premium, claims and conversion indicators')}<div class="core-note">${esc(d.basis_note)}</div></div><div class="core-metrics">${metrics.map(([k,v])=>`<div class="core-metric"><span>${esc(k)}</span><strong>${v}</strong><small>As at ${dt(d.generated_at)}</small></div>`).join('')}</div>`;
  }

  async function renderAdvancedClaims(){
    const rows=await api('/claims?limit=500');
    pageContent.innerHTML=`<div class="panel">${toolbar('Advanced claims workflow','Activities, assessment history and controlled settlements')}${rowsTable(['Claim','Policy','Loss date','Reserve','Approved','Excess','Status',''],rows.map(x=>`<tr><td>${esc(x.reference)}</td><td>${esc(x.policy_number)}</td><td>${dte(x.loss_date)}</td><td>${money(x.reserve_amount)}</td><td>${money(x.approved_amount)}</td><td>${money(x.excess_amount)}</td><td>${badge(x.status)}</td><td><div class="core-actions"><button data-clm-activity="${x.id}">Activity</button><button data-clm-history="${x.id}">History</button><button data-clm-pay="${x.id}">Settlement</button></div></td></tr>`))}</div>`;
    pageContent.querySelectorAll('[data-clm-activity]').forEach(b=>b.onclick=()=>claimActivityModal(rows.find(x=>x.id===Number(b.dataset.clmActivity))));
    pageContent.querySelectorAll('[data-clm-history]').forEach(b=>b.onclick=()=>showClaimHistory(rows.find(x=>x.id===Number(b.dataset.clmHistory))));
    pageContent.querySelectorAll('[data-clm-pay]').forEach(b=>b.onclick=()=>claimSettlementModal(rows.find(x=>x.id===Number(b.dataset.clmPay))));
  }
  function claimActivityModal(x){const fields=[{name:'activity_type',label:'Activity',type:'select',options:['Coverage Check','Assessment','Document Review','Investigation','Approval','Customer Contact','Recovery','Closure'].map(v=>({value:v,label:v}))},{name:'status',label:'Claim status',type:'select',options:[{value:'',label:'Do not change'},...['Registered','Assessing','Awaiting Documents','Approved','Rejected','Paid','Closed'].map(v=>({value:v,label:v}))]},{name:'amount',label:'Activity amount (optional)',type:'number',step:'0.01'},{name:'notes',label:'Activity notes',type:'textarea',full:true}];openModal({title:x.reference,eyebrow:'Claim activity',fields,onSubmit:data=>api(`/core/claims/${x.id}/activities`,{method:'POST',body:data})})}
  function claimSettlementModal(x){const fields=[{name:'amount',label:'Settlement amount',type:'number',step:'0.01',required:true},{name:'payment_type',label:'Payment type',type:'select',options:['Settlement','Partial Settlement','Supplier Payment','Recovery Refund'].map(v=>({value:v,label:v})),value:'Settlement'},{name:'status',label:'Status',type:'select',options:['Approved','Paid','Cancelled'].map(v=>({value:v,label:v})),value:'Approved'},{name:'payment_reference',label:'Payment reference'}];openModal({title:x.reference,eyebrow:'Claim settlement',fields,onSubmit:data=>api(`/core/claims/${x.id}/settlements`,{method:'POST',body:data})})}
  async function showClaimHistory(x){try{const d=await api(`/core/claims/${x.id}/history`);openModal({title:`${x.reference} history`,eyebrow:'Claims workflow',fields:[],submit:'Close',onSubmit:async()=>{}});modalForm.innerHTML=`<div class="full"><h3>Activities</h3>${rowsTable(['Activity','Status','Amount','Notes','Time'],d.activities.map(a=>`<tr><td>${esc(a.activity_type)}</td><td>${esc(a.status||'—')}</td><td>${a.amount==null?'—':money(a.amount)}</td><td class="wrap">${esc(a.notes||'—')}</td><td>${dt(a.created_at)}</td></tr>`))}<h3 style="margin-top:18px">Settlements</h3>${rowsTable(['Reference','Type','Amount','Status','Paid'],d.settlements.map(s=>`<tr><td>${esc(s.reference)}</td><td>${esc(s.payment_type)}</td><td>${money(s.amount)}</td><td>${badge(s.status)}</td><td>${dt(s.paid_at)}</td></tr>`))}</div><div class="modal-actions"><button type="button" class="primary" data-close-modal>Close</button></div>`}catch(err){toast(err.message)}}

  pages.underwriting=['Underwriting & Quotes','Core insurance',renderUnderwriting];
  pages.lifecycle=['Policy Lifecycle','Core insurance',renderLifecycle];
  pages.customer360=['Customer 360','Customer intelligence',renderCustomer360];
  pages.advancedClaims=['Claims Workflow','Core insurance',renderAdvancedClaims];
  pages.intermediaries=['Agents & Brokers','Distribution',renderIntermediaries];
  pages.executive=['Executive Dashboard','Management reporting',renderExecutive];
})();
