(() => {
  const base = window.DERMASCAN_API_URL || (location.hostname === 'pablinvb.github.io' ? 'https://dermascan-ai-api.onrender.com' : location.port === '8000' ? '' : 'http://127.0.0.1:8000');
  let token = sessionStorage.getItem('evamcare-account') || '', selected = '', user;
  const originalFetch = window.fetch.bind(window);
  window.fetch = (input, options = {}) => {
    const url = new URL(typeof input === 'string' ? input : input.url, location.href);
    const apiOrigin = new URL(base || location.origin).origin;
    if (token && url.origin === apiOrigin && url.pathname.startsWith('/api/v1/')) {
      const headers = new Headers(options.headers);
      headers.set('Authorization', `Bearer ${token}`);
      if (selected) headers.set('X-Patient-ID', selected);
      options = {...options, headers};
    }
    return originalFetch(input, options);
  };
  const section = document.createElement('section');
  section.className = 'section'; section.id = 'accounts';
  section.innerHTML = `<h2>Cuenta y acceso profesional</h2><p id="account-message" role="status"></p><form id="account-login"><label>Correo <input name="email" type="email" required autocomplete="username"></label><label>Contraseña <input name="password" type="password" minlength="12" required autocomplete="current-password"></label><button>Iniciar sesión</button></form><form id="account-activate"><label>Token de invitación <input name="token" required></label><label>Nueva contraseña <input name="password" type="password" minlength="12" required autocomplete="new-password"></label><button>Activar cuenta</button></form><div id="account-portal" hidden><button id="account-logout">Cerrar sesión</button><div id="account-admin" hidden><h3>Gestión de usuarios</h3><input id="user-search" placeholder="Nombre, correo o Dermascan ID"><select id="user-role"><option value="">Todos los roles</option><option>admin</option><option>evaluator</option><option>patient</option><option>professional</option></select><select id="user-status"><option value="">Todos los estados</option><option>active</option><option>inactive</option><option>pending</option></select><button id="users-load">Buscar usuarios</button><div id="users-list"></div></div><form id="account-invite" hidden><h3>Crear cuenta / paciente</h3><input name="name" placeholder="Nombre completo" required><input name="email" type="email" placeholder="Correo único" required><select name="role"><option value="patient">Paciente</option><option value="evaluator">Evaluador</option><option value="professional">Profesional</option></select><input name="specialty" placeholder="Especialidad profesional"><button>Crear invitación</button></form><div id="account-directory" hidden><h3>Pacientes</h3><input id="patient-search" placeholder="Nombre, correo o Dermascan ID"><button id="patients-load">Buscar pacientes</button><div id="patients-list"></div></div><div id="account-sharing" hidden><h3>Compartir con profesional</h3><form id="grant-form"><select name="professional" required></select><label><input name="profile" type="checkbox">Perfil</label><label><input name="scans" type="checkbox">Resultados</label><label><input name="evolution" type="checkbox">Evolución</label><label><input name="recommendations" type="checkbox">Recomendaciones</label><p>Las fotografías no se almacenan actualmente.</p><input name="hours" type="number" min="1" max="720" value="72" required><button>Autorizar acceso</button></form></div><div id="account-grants" hidden><h3>Mis pacientes compartidos / permisos</h3><div id="grants-list"></div></div><div id="account-record"></div></div>`;
  document.querySelector('main').append(section);
  const consent=document.createElement('label');
  consent.innerHTML='<input id="patient-account-consent" type="checkbox"> Confirmo el consentimiento del paciente seleccionado para esta evaluación y su registro.';
  document.querySelector('#save-history').parentElement.insertAdjacentElement('afterend',consent);
  const $ = s => section.querySelector(s);
  const message = text => $('#account-message').textContent = text;
  const action = fn => async e => {e?.preventDefault(); try {await fn(e);} catch(error) {message(error.message);}};
  async function api(path, body, method = 'GET') {
    const response = await fetch(`${base}/api/v1/accounts${path}`, {method, headers:{'Content-Type':'application/json'}, ...(body ? {body:JSON.stringify(body)} : {})});
    const data = await response.json(); if (!response.ok) throw Error(typeof data.detail === 'string' ? data.detail : 'Revisa los campos de la solicitud'); return data;
  }
  function list(target, items, render) {target.replaceChildren(); items.forEach(item => {const row=document.createElement('div'); row.className='history-card'; render(row,item);target.append(row);});}
  function button(row,text,fn) {const b=document.createElement('button');b.type='button';b.textContent=text;b.onclick=action(fn);row.append(b);}
  async function openRecord(pid) {const data=await api(`/patients/${pid}/record`);$('#account-record').replaceChildren();const pre=document.createElement('pre');pre.style.whiteSpace='pre-wrap';pre.textContent=JSON.stringify(data,null,2);$('#account-record').append(pre);if(user.roles.includes('professional')) {const textarea=document.createElement('textarea');textarea.placeholder='Nota privada de seguimiento';$('#account-record').append(textarea);button($('#account-record'),'Guardar nota',async()=>{await api(`/patients/${pid}/notes`,{body:textarea.value},'POST');message('Nota privada guardada');});}}
  async function grants() {list($('#grants-list'),(await api('/grants')).items,(row,g)=>{row.textContent=`${g.first_name} · ${g.professional_name} · ${g.revoked_at ? 'Revocado' : g.expires_at}`;if(user.roles.includes('patient'))button(row,'Revocar',async()=>{await api(`/grants/${g.id}/revoke`,{},'POST');await grants();});if(user.roles.includes('professional'))button(row,'Ver expediente',()=>openRecord(g.patient_id));});}
  async function refresh() {
    user=await api('/me');message(`${user.name} · ${user.roles.join(', ')}`);$('#account-login').hidden=true;$('#account-activate').hidden=true;$('#account-portal').hidden=false;
    $('#account-admin').hidden=!user.roles.includes('admin');$('#account-directory').hidden=!user.roles.some(r=>['admin','evaluator'].includes(r));$('#account-invite').hidden=$('#account-directory').hidden;
    $('#account-invite [name=role]').disabled=!user.roles.includes('admin');$('#account-sharing').hidden=!user.roles.includes('patient');$('#account-grants').hidden=!user.roles.some(r=>['patient','professional'].includes(r));
    if(user.roles.includes('patient')) {const select=$('#grant-form [name=professional]'); select.replaceChildren();(await api('/professionals')).items.forEach(p=>{const o=document.createElement('option');o.value=p.id;o.textContent=`${p.name} · ${p.specialty || 'Profesional'}`;select.append(o);});await openRecord(user.patient_id);}
    if(!$('#account-grants').hidden)await grants();
    if(user.roles.includes('patient'))window.dispatchEvent(new Event('evamcare-patient-context'));
  }
  $('#account-login').onsubmit=action(async e=>{const body=Object.fromEntries(new FormData(e.target));token=(await api('/login',body,'POST')).token;sessionStorage.setItem('evamcare-account',token);await refresh();});
  $('#account-activate').onsubmit=action(async e=>{await api('/activate',Object.fromEntries(new FormData(e.target)),'POST');e.target.reset();message('Cuenta activada. Inicia sesión.');});
  $('#account-logout').onclick=action(async()=>{await api('/logout',{},'POST');sessionStorage.removeItem('evamcare-account');location.reload();});
  $('#account-invite').onsubmit=action(async e=>{const d=Object.fromEntries(new FormData(e.target));const invitation=await api('/invite',{name:d.name,email:d.email,roles:[d.role],specialty:d.specialty||null},'POST');message(`Invitación creada. Token de activación (48 horas): ${invitation.activationToken}. Paciente: ${invitation.patientId || 'No aplica'}`);});
  $('#users-load').onclick=action(async()=>{const params=new URLSearchParams({q:$('#user-search').value,role:$('#user-role').value,status:$('#user-status').value});list($('#users-list'),(await api('/users?'+params)).items,(row,u)=>{row.textContent=`${u.name} · ${u.email} · ${u.roles.join(', ')} · ${u.status} · ${u.created_at}`;button(row,'Activar / desactivar',async()=>{await api('/users/'+u.id,{name:u.name,status:u.status==='active'?'inactive':'active',roles:u.roles},'PUT');$('#users-load').click();});});});
  $('#patients-load').onclick=action(async()=>{list($('#patients-list'),(await api('/patients?q='+encodeURIComponent($('#patient-search').value))).items,(row,p)=>{row.textContent=`${p.first_name} · ${p.patient_code} · ${p.scan_count} escaneos · ${p.last_evaluation || 'Sin evaluación'}`;button(row,'Ver expediente',()=>openRecord(p.id));button(row,'Nueva evaluación',async()=>{await api(`/patients/${p.id}/record`);selected=p.id;message(`Evaluación seleccionada: ${p.first_name} (${p.patient_code}). Confirma el consentimiento antes de escanear.`);document.querySelector('#scanner').scrollIntoView({behavior:'smooth'});});});});
  $('#grant-form').onsubmit=action(async e=>{const d=new FormData(e.target);await api('/grants',{professionalId:d.get('professional'),hours:Number(d.get('hours')),scopes:['profile','scans','evolution','recommendations'].filter(s=>d.has(s))},'POST');await grants();message('Acceso autorizado');});
  const nav=document.querySelector('nav');if(nav){const link=document.createElement('a');link.href='#accounts';link.textContent='Mi cuenta';nav.append(link);}
  const editForm=document.createElement('form');
  editForm.hidden=true;
  editForm.innerHTML='<h3>Editar cuenta</h3><input name="id" readonly required><input name="name" placeholder="Nombre" required><select name="status"><option>active</option><option>inactive</option><option>pending</option></select><label><input name="admin" type="checkbox">Administrador</label><label><input name="evaluator" type="checkbox">Evaluador</label><label><input name="patient" type="checkbox">Paciente</label><label><input name="professional" type="checkbox">Profesional</label><button>Guardar cambios</button>';
  $('#account-admin').append(editForm);
  const loadUsers=$('#users-load').onclick;
  $('#users-load').onclick=action(async e=>{await loadUsers(e);const params=new URLSearchParams({q:$('#user-search').value,role:$('#user-role').value,status:$('#user-status').value});const items=(await api('/users?'+params)).items;[...$('#users-list').children].forEach((row,i)=>button(row,'Editar perfil y roles',()=>{const u=items[i];editForm.hidden=false;editForm.elements.id.value=u.id;editForm.elements.name.value=u.name;editForm.elements.status.value=u.status;['admin','evaluator','patient','professional'].forEach(r=>editForm.elements[r].checked=u.roles.includes(r));}));});
  editForm.onsubmit=action(async e=>{const d=new FormData(e.target);await api('/users/'+d.get('id'),{name:d.get('name'),status:d.get('status'),roles:['admin','evaluator','patient','professional'].filter(r=>d.has(r))},'PUT');message('Cuenta actualizada');$('#users-load').click();});
  const assignment=document.createElement('form');
  assignment.innerHTML='<h3>Autorizar evaluador para paciente</h3><input name="patientId" placeholder="ID interno del paciente" required><input name="evaluatorId" placeholder="ID interno del evaluador" required><button>Asignar evaluador</button>';
  $('#account-admin').append(assignment);
  assignment.onsubmit=action(async e=>{await api('/assignments',Object.fromEntries(new FormData(e.target)),'POST');message('Evaluador autorizado para este paciente');});
  const grantSearch=document.createElement('input');grantSearch.placeholder='Buscar pacientes compartidos';$('#account-grants').prepend(grantSearch);
  grantSearch.oninput=()=>{[...$('#grants-list').children].forEach(row=>row.hidden=!row.textContent.toLowerCase().includes(grantSearch.value.toLowerCase()));};
  if(token)refresh().catch(error=>{token='';sessionStorage.removeItem('evamcare-account');message(error.message);});
})();
