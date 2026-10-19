/* version 5 */
// Mount path from <html data-base> when served under the SWSuite proxy (/kick); "" standalone.
function url(path){return (document.documentElement.dataset.base||'')+path}
function el(id){return document.getElementById(id)}
function notify(message,error=false){
  const n=document.createElement('div');
  n.className='flash-notice'+(error?' is-error':'');
  n.textContent=message;
  document.body.appendChild(n);
  setTimeout(()=>n.remove(),4500);
}
function toggleTheme(){
  const next=document.documentElement.dataset.theme==='light'?'dark':'light';
  document.documentElement.dataset.theme=next;
  try{localStorage.setItem('kicker_theme',next)}catch(e){}
}
function openConsole(title){
  const modal=el('console-modal');
  if(!modal){notify('Console is unavailable on this page',true);return}
  el('console-title').textContent=title;
  el('console-out').textContent='';
  modal.classList.remove('hidden');
  modal.querySelector('button')?.focus();
}
function closeConsole(){el('console-modal')?.classList.add('hidden')}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeConsole()});
async function readResponse(response){
  const data=await response.json().catch(()=>({}));
  if(!response.ok){
    const detail=typeof data.detail==='string'?data.detail:'Request failed ('+response.status+')';
    throw new Error(detail);
  }
  return data;
}
async function streamJob(jobId){
  const out=el('console-out');
  const es=new EventSource(url('/jobs/'+jobId+'/stream'));
  es.onmessage=e=>{out.textContent+=e.data+'\n';out.scrollTop=out.scrollHeight};
  es.addEventListener('done',()=>{es.close();setTimeout(()=>location.reload(),1100)});
  es.onerror=()=>{es.close();notify('Live stream disconnected. Check Logs for job status.',true)};
}
async function runUpgrade(hostId,name){
  if(!confirm('Run apt update & upgrade on '+name+'?'))return;
  openConsole('Upgrading '+name);
  try{const data=await readResponse(await fetch(url('/hosts/'+hostId+'/upgrade'),{method:'POST'}));streamJob(data.job_id)}
  catch(e){if(el('console-out'))el('console-out').textContent=e.message;notify(e.message,true)}
}
async function checkHost(hostId,name,button=null){
  if(button){
    if(button.getAttribute('aria-busy')==='true')return;
    button.disabled=true;
    button.setAttribute('aria-busy','true');
  }
  notify('Checking updates on '+name+'…');
  try{
    const result=await readResponse(await fetch(url('/hosts/'+hostId+'/check'),{method:'POST'}));
    const job=await readResponse(await fetch(url('/jobs/'+result.job_id+'/output')));
    notify(job.status==='success'?'Host check completed':'Host check failed',job.status!=='success');
    location.reload();
  }catch(e){notify(e.message,true)}
  finally{
    if(button){button.disabled=false;button.setAttribute('aria-busy','false')}
  }
}
async function checkAll(button){
  if(button){
    if(button.getAttribute('aria-busy')==='true')return;
    button.disabled=true;
    button.setAttribute('aria-busy','true');
  }
  notify('Checking all hosts. This may take a moment…');
  try{await readResponse(await fetch(url('/check-all'),{method:'POST'}));location.reload()}
  catch(e){
    notify(e.message,true);
    if(button){button.disabled=false;button.setAttribute('aria-busy','false')}
  }
}
let activeHostFilter='all';
function setHostFilter(value){
  activeHostFilter=value;
  document.querySelectorAll('[data-host-filter]').forEach(b=>{
    const active=b.dataset.hostFilter===value;
    b.classList.toggle('is-selected',active);
    b.setAttribute('aria-pressed',String(active));
  });
  filterHosts();
}
function filterHosts(){
  const term=(el('host-search')?.value||'').trim().toLowerCase();
  let shown=0;
  document.querySelectorAll('[data-host-card]').forEach(card=>{
    const st=card.dataset.status;
    const match=(card.dataset.search||'').includes(term);
    const matchesStatus=activeHostFilter==='all'||(activeHostFilter==='updates'&&(st==='some'||st==='many'))||(activeHostFilter==='online'&&st!=='offline'&&st!=='unknown')||st===activeHostFilter;
    const visible=match&&matchesStatus;
    card.hidden=!visible;
    if(visible)shown++;
  });
  document.querySelectorAll('[data-host-group]').forEach(g=>{
    g.hidden=!g.querySelector('[data-host-card]:not([hidden])');
  });
  const empty=el('filter-empty');
  if(empty)empty.hidden=shown!==0||!document.querySelector('[data-host-card]');
}
function filterRows(input,tableId){
  const term=input.value.toLowerCase();
  document.querySelectorAll('#'+tableId+' tbody tr').forEach(row=>row.hidden=!row.textContent.toLowerCase().includes(term));
}
function syncCredentialFields(){
  const type=el('credential-type')?.value;
  if(!type)return;
  document.querySelectorAll('[data-credential-type]').forEach(group=>{
    const visible=group.dataset.credentialType===type;
    group.hidden=!visible;
    group.querySelectorAll('input,textarea').forEach(field=>{field.disabled=!visible});
  });
}
function updateGroupEmpty(){
  const list=el('host-group-list'),empty=el('host-group-empty');
  if(list&&empty)empty.hidden=Boolean(list.querySelector('[data-group-id]'));
}
function appendHostGroup(group){
  const list=el('host-group-list');
  if(!list)return;
  const row=document.createElement('div');
  row.className='group-choice';
  row.dataset.groupId=String(group.id);

  const label=document.createElement('label');
  label.className='check';
  label.htmlFor='host-group-'+group.id;
  const checkbox=document.createElement('input');
  checkbox.type='checkbox';
  checkbox.id='host-group-'+group.id;
  checkbox.name='group_ids';
  checkbox.value=String(group.id);
  checkbox.checked=true;
  const name=document.createElement('span');
  const title=group.dimension_label+': '+group.name;
  name.textContent=title;
  label.append(checkbox,name);

  const remove=document.createElement('button');
  remove.type='button';
  remove.className='group-remove';
  remove.textContent='×';
  remove.title='Delete group for all hosts';
  remove.setAttribute('aria-label','Delete '+group.name+' group');
  remove.addEventListener('click',()=>removeHostGroup(group.id,title));
  row.append(label,remove);
  list.appendChild(row);
  updateGroupEmpty();
}
async function addHostGroup(button){
  const dimension=el('quick-group-dimension')?.value;
  const name=el('quick-group-name')?.value.trim();
  if(!name){notify('Enter a group name first.',true);el('quick-group-name')?.focus();return}
  if(button)button.disabled=true;
  try{
    const data=await readResponse(await fetch(url('/groups/quick-create'),{
      method:'POST',
      body:new URLSearchParams({dimension,name}),
    }));
    appendHostGroup(data);
    el('quick-group-name').value='';
    notify('Group created and selected.');
  }catch(e){notify(e.message,true)}
  finally{if(button)button.disabled=false}
}
async function removeHostGroup(groupId,groupName){
  if(!confirm('Delete '+groupName+'? This removes the group from every host.'))return;
  try{
    await readResponse(await fetch(url('/groups/'+groupId+'/quick-delete'),{method:'POST'}));
    const row=document.querySelector('[data-group-id="'+groupId+'"]');
    if(row)row.remove();
    updateGroupEmpty();
    notify('Group removed.');
  }catch(e){notify(e.message,true)}
}
if(el('credential-type'))syncCredentialFields();


function openCredentialDialog(){
  const dialog=el('quick-credential-dialog');
  if(!dialog)return;
  el('quick-credential-error').hidden=true;
  syncQuickCredentialFields();
  if(!dialog.open)dialog.showModal();
  el('quick-credential-name').focus();
}
function closeCredentialDialog(){
  const dialog=el('quick-credential-dialog');
  if(dialog?.open)dialog.close();
}
function syncQuickCredentialFields(){
  const type=el('quick-credential-type')?.value;
  document.querySelectorAll('[data-quick-credential-type]').forEach(group=>{
    const active=group.dataset.quickCredentialType===type;
    group.hidden=!active;
    group.querySelectorAll('input,textarea').forEach(field=>{
      field.disabled=!active;
      if(field.name==='password'||field.name==='private_key')field.required=active;
    });
  });
}
async function saveQuickCredential(event){
  event.preventDefault(); // Never submit or reset the surrounding host form.
  const form=el('quick-credential-form');
  const button=el('quick-credential-save');
  const error=el('quick-credential-error');
  if(!form||!button||button.disabled)return;
  error.hidden=true;
  button.disabled=true;
  button.setAttribute('aria-busy','true');
  try{
    const response=await fetch(form.action,{
      method:'POST',
      body:new FormData(form),
      headers:{'Accept':'application/json'},
    });
    const credential=await readResponse(response);
    if(!Number.isSafeInteger(credential.id)||credential.id<1){
      throw new Error('Credential was not created. Please retry.');
    }
    const select=el('host-credential');
    if(!select)throw new Error('Host credential selector is missing.');
    const option=new Option(credential.name,String(credential.id),true,true);
    select.add(option);
    select.value=String(credential.id);
    form.reset();
    syncQuickCredentialFields();
    closeCredentialDialog();
    notify('Credential saved and selected for this host.');
  }catch(e){
    error.textContent=e.message||'Unable to create credential.';
    error.hidden=false;
  }finally{
    button.disabled=false;
    button.setAttribute('aria-busy','false');
  }
}
