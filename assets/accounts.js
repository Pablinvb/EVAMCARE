(() => {
  const base = window.DERMASCAN_API_URL || (location.hostname === 'pablinvb.github.io' ? 'https://dermascan-ai-api.onrender.com' : location.port === '8000' || location.hostname.endsWith('.onrender.com') ? '' : 'http://127.0.0.1:8000');
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
  const datasetLabel = document.createElement('label');
  datasetLabel.textContent = 'Tipo de expediente ';
  const datasetSelect = document.createElement('select');
  datasetSelect.name = 'dataset';
  for (const [value, text] of [['test', 'Ficticio / demostración'], ['real', 'Paciente real (requiere consentimiento)']]) {
    const option = document.createElement('option');
    option.value = value; option.textContent = text; datasetSelect.append(option);
  }
  datasetLabel.append(datasetSelect);
  section.querySelector('#account-invite').insertBefore(datasetLabel, section.querySelector('#account-invite button'));
  document.querySelector('main').append(section);
  const consent=document.createElement('label');
  consent.innerHTML='<input id="patient-account-consent" type="checkbox"> Confirmo el consentimiento del paciente seleccionado para esta evaluación y su registro.';
  document.querySelector('#save-history').parentElement.insertAdjacentElement('afterend',consent);
  const $ = s => section.querySelector(s);
  const message = text => $('#account-message').textContent = text;
  const action = fn => async e => {e?.preventDefault();const submit=e?.target?.querySelector?.('button[type=submit],button:not([type])');if(submit)submit.disabled=true;try {await fn(e);} catch(error) {message(error instanceof TypeError || error.name==='AbortError'?'No se pudo conectar con el servidor. Inténtalo nuevamente.':error.message);}finally{if(submit)submit.disabled=false;}};
  async function api(path, body, method = 'GET') {
    let response;
    for(let attempt=0;attempt<2;attempt++){
      try{response=await fetch(`${base}/api/v1/accounts${path}`, {method,signal:AbortSignal.timeout(25000),headers:{'Content-Type':'application/json'}, ...(body ? {body:JSON.stringify(body)} : {})});break;}
      catch(error){if(method!=='GET'||attempt)throw Error('No se pudo conectar con el servidor. Inténtalo nuevamente.');await new Promise(resolve=>setTimeout(resolve,800));}
    }
    const data=await response.json().catch(()=>({}));
    if(!response.ok)throw Error(response.status>=500?'El servidor no está disponible temporalmente. Inténtalo nuevamente.':data.error?.message || (typeof data.detail==='string'?data.detail:'Revisa los campos de la solicitud'));return data;
  }
  function list(target, items, render) {target.replaceChildren(); items.forEach(item => {const row=document.createElement('div'); row.className='history-card'; render(row,item);target.append(row);});}
  function button(row,text,fn) {const b=document.createElement('button');b.type='button';b.textContent=text;b.onclick=action(fn);row.append(b);}
  async function openRecord(pid) {
    message('Cargando expediente…');const data=await api(`/patients/${pid}/record`);const target=$('#account-record');target.replaceChildren();
    const names={patient:'Datos generales',scans:'Historial de evaluaciones',evolution:'Evolución de métricas',recommendations:'Recomendaciones'};
    const draw=(parent,value)=>{if(value===null||value===undefined)return;if(Array.isArray(value)){if(!value.length){const p=document.createElement('p');p.textContent='Sin registros todavía.';parent.append(p);}value.forEach(item=>{const card=document.createElement('article');card.className='history-card';draw(card,item);parent.append(card);});}else if(typeof value==='object'){const dl=document.createElement('dl');Object.entries(value).filter(([k])=>!['session_id','analysis_payload_json','analysisPayload'].includes(k)).forEach(([k,v])=>{const dt=document.createElement('dt');dt.textContent=k.replaceAll('_',' ');const dd=document.createElement('dd');draw(dd,v);dl.append(dt,dd);});parent.append(dl);}else parent.append(document.createTextNode(String(value)));};
    Object.entries(data).forEach(([key,value])=>{const block=document.createElement('section');const title=document.createElement('h3');title.textContent=names[key]||key;block.append(title);draw(block,value);target.append(block);});
    if(user.roles.some(r=>['patient','evaluator'].includes(r)))button(target,'Nueva evaluación',()=>{selected=pid;document.querySelector('#patient-account-consent').checked=false;message('Confirma el consentimiento antes de realizar la reevaluación.');document.querySelector('[data-start-scan]').click();});
    if(user.roles.includes('professional')) {const textarea=document.createElement('textarea');textarea.placeholder='Nota privada de seguimiento';target.append(textarea);button(target,'Guardar nota',async()=>{await api(`/patients/${pid}/notes`,{body:textarea.value},'POST');message('Nota privada guardada');});button(target,'Consultar mis notas',async()=>{const notes=await api(`/patients/${pid}/notes`);draw(target,notes.items);});}
    message('Expediente cargado. Solo se muestran los datos autorizados.');
  }
  async function grants() {list($('#grants-list'),(await api('/grants')).items,(row,g)=>{row.textContent=`${g.first_name} · ${g.professional_name} · ${g.revoked_at ? 'Revocado' : g.expires_at}`;if(user.roles.includes('patient'))button(row,'Revocar',async()=>{await api(`/grants/${g.id}/revoke`,{},'POST');await grants();});if(user.roles.includes('professional'))button(row,'Ver expediente',()=>openRecord(g.patient_id));});}
  async function refresh() {
    user=await api('/me');message(`${user.name} · ${user.roles.join(', ')}`);$('#account-login').hidden=true;$('#account-activate').hidden=true;$('#account-portal').hidden=false;
    $('#account-admin').hidden=!user.roles.includes('admin');$('#account-directory').hidden=!user.roles.some(r=>['admin','evaluator'].includes(r));$('#account-invite').hidden=$('#account-directory').hidden;
    $('#account-invite [name=role]').disabled=!user.roles.includes('admin');$('#account-sharing').hidden=!user.roles.includes('patient');$('#account-grants').hidden=!user.roles.some(r=>['patient','professional'].includes(r));
    if(user.roles.includes('patient')) {const select=$('#grant-form [name=professional]'); select.replaceChildren();(await api('/professionals')).items.forEach(p=>{const o=document.createElement('option');o.value=p.id;o.textContent=`${p.name} · ${p.specialty || 'Profesional'}`;select.append(o);});await openRecord(user.patient_id);}
    if(!$('#account-grants').hidden)await grants();
    if(user.roles.includes('patient'))window.dispatchEvent(new Event('evamcare-patient-context'));
    window.dispatchEvent(new CustomEvent('evamcare-auth', {detail:user}));
  }
  $('#account-login').onsubmit=action(async e=>{const body=Object.fromEntries(new FormData(e.target));token=(await api('/login',body,'POST')).token;sessionStorage.setItem('evamcare-account',token);await refresh();});
  $('#account-activate').onsubmit=action(async e=>{await api('/activate',Object.fromEntries(new FormData(e.target)),'POST');e.target.reset();message('Cuenta activada. Inicia sesión.');});
  $('#account-logout').onclick=action(async()=>{await api('/logout',{},'POST');sessionStorage.removeItem('evamcare-account');location.reload();});
  function showInvitation(invitation) {
    message(invitation.message || 'Invitación creada. Comparte el enlace privado con la persona invitada.');
    const link=document.createElement('a');
    link.href=location.origin+location.pathname+'#/activate-account?token='+encodeURIComponent(invitation.activationToken);
    link.textContent='Abrir enlace privado de activación (48 horas)';
    $('#account-message').append(document.createElement('br'),link);
    button($('#account-message'),'Copiar enlace privado',async()=>{
      await navigator.clipboard.writeText(link.href);
      const confirmation=document.createElement('span');confirmation.textContent=' Enlace copiado; compártelo solo con el destinatario.';
      $('#account-message').append(confirmation);
    });
  }
  $('#account-invite').onsubmit=action(async e=>{const d=Object.fromEntries(new FormData(e.target));const invitation=await api('/invite',{name:d.name,email:d.email,roles:[d.role],specialty:d.specialty||null,dataset:d.dataset},'POST');showInvitation(invitation);});
  $('#users-load').onclick=action(async()=>{const params=new URLSearchParams({q:$('#user-search').value,role:$('#user-role').value,status:$('#user-status').value});list($('#users-list'),(await api('/users?'+params)).items,(row,u)=>{row.textContent=`${u.name} · ${u.email} · ${u.roles.join(', ')} · ${u.status} · ${u.created_at}`;if(u.status==='pending'){button(row,'Regenerar / reenviar invitación',async()=>{showInvitation(await api('/users/'+u.id+'/resend-invitation',{},'POST'));});}else{button(row,'Activar / desactivar',async()=>{await api('/users/'+u.id,{name:u.name,status:u.status==='active'?'inactive':'active',roles:u.roles},'PUT');$('#users-load').click();});}});});
  $('#patients-load').onclick=action(async()=>{list($('#patients-list'),(await api('/patients?q='+encodeURIComponent($('#patient-search').value))).items,(row,p)=>{row.textContent=`${p.first_name} · ${p.patient_code} · ${p.scan_count} escaneos · ${p.last_evaluation || 'Sin evaluación'}`;button(row,'Ver expediente',()=>openRecord(p.id));button(row,'Nueva evaluación',async()=>{await api(`/patients/${p.id}/record`);selected=p.id;document.querySelector('#patient-account-consent').checked=false;message(`Evaluación seleccionada: ${p.first_name} (${p.patient_code}). Confirma el consentimiento antes de escanear.`);document.querySelector('[data-start-scan]').click();});});});
  $('#grant-form').onsubmit=action(async e=>{const d=new FormData(e.target);await api('/grants',{professionalId:d.get('professional'),hours:Number(d.get('hours')),scopes:['profile','scans','evolution','recommendations','photographs'].filter(s=>d.has(s))},'POST');await grants();message('Acceso autorizado');});
  const photoScope=document.createElement('label');photoScope.innerHTML='<input name="photographs" type="checkbox">Fotografías adjuntas';$('#grant-form').prepend(photoScope);
  const privacy=document.createElement('section');
  privacy.innerHTML='<h3>Privacidad y control de mis datos</h3><p>Evaluación cosmética orientativa, no diagnóstico médico. Compartir es opcional y revocable.</p><a href="#/privacy">Leer aviso de privacidad</a><button type="button" id="privacy-export">Descargar mi expediente</button><form id="privacy-erasure"><h4>Solicitar eliminación</h4><p>Se revocarán sesiones y accesos. La eliminación física se tramita por separado.</p><label>Confirma tu contraseña<input name="password" type="password" required minlength="12" autocomplete="current-password"></label><label>Escribe SOLICITAR ELIMINACIÓN<input name="confirmation" required></label><button>Enviar solicitud</button></form>';
  $('#account-sharing').append(privacy);
  const consentForm=document.createElement('form');consentForm.innerHTML='<h4>Consentimiento de evaluación</h4><label><input name="informed" type="checkbox" required>He leído el aviso: entiendo el análisis cosmético, sus límites y el registro de resultados.</label><label><input name="adult" type="checkbox" required>Declaro que soy mayor de edad.</label><button>Autorizar evaluación e historial</button><button type="button" id="withdraw-evaluation">Retirar consentimiento</button>';privacy.prepend(consentForm);
  async function privacyAPI(path,body){const response=await fetch(`${base}/api/v1/privacy${path}`,{method:body?'POST':'GET',headers:{'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});const data=await response.json();if(!response.ok)throw Error(data.detail||'No se pudo completar la solicitud');return data;}
  consentForm.onsubmit=action(async e=>{const notice=await privacyAPI('/notice');await privacyAPI('/consent',{purpose:'evaluation',granted:true,adult:new FormData(e.target).has('adult'),version:notice.version});message('Consentimiento registrado. Puedes retirarlo cuando lo desees.');});
  $('#withdraw-evaluation').onclick=action(async()=>{const notice=await privacyAPI('/notice');await privacyAPI('/consent',{purpose:'evaluation',granted:false,version:notice.version});message('Consentimiento retirado; esto no equivale a borrar el expediente.');});
  $('#privacy-export').onclick=action(async()=>{const data=await privacyAPI('/export');const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='mi-expediente-evamcare.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  $('#privacy-erasure').onsubmit=action(async e=>{const data=await privacyAPI('/erasure',Object.fromEntries(new FormData(e.target)));e.target.reset();sessionStorage.removeItem('evamcare-account');token='';selected='';message(data.message);location.hash='#/login';});
  const notice=document.createElement('div');notice.id='privacy-notice';notice.hidden=true;section.append(notice);
  window.addEventListener('DOMContentLoaded',()=>{if(location.hash==='#/privacy')window.dispatchEvent(new Event('hashchange'));});
  window.addEventListener('hashchange',async()=>{notice.hidden=location.hash!=='#/privacy';if(notice.hidden)return;try{const data=await privacyAPI('/notice');notice.replaceChildren();Object.entries(data).forEach(([key,value])=>{const p=document.createElement('p');p.textContent=key+': '+(Array.isArray(value)?value.join(', '):value||'Pendiente de configurar');notice.append(p);});}catch(error){notice.textContent='Aviso no disponible. No continúes con pacientes reales.';}});
  consent.append(document.createTextNode(' He explicado los límites del análisis, el procesamiento de la captura y el historial. '));const noticeLink=document.createElement('a');noticeLink.href='#/privacy';noticeLink.textContent='Aviso de privacidad';consent.append(noticeLink);
  $('#grant-form p').textContent='El escáner no guarda fotografías por defecto. Puedes adjuntarlas opcionalmente con consentimiento cuando el almacenamiento privado esté configurado.';
  const originalOpenRecord=openRecord;
  openRecord=async pid=>{
    await originalOpenRecord(pid);
    const target=$('#account-record');
    button(target,'Consultar fotografías autorizadas',async()=>{
      const photos=await api(`/patients/${pid}/photos`);
      photos.items.forEach(photo=>button(target,'Ver fotografía de '+photo.created_at,async()=>{
        const response=await fetch(`${base}/api/v1/accounts/patients/${pid}/photos/${photo.id}`);
        if(!response.ok)throw Error('Fotografía no autorizada o almacenamiento no disponible');
        const objectUrl=URL.createObjectURL(await response.blob());const image=document.createElement('img');image.alt='Fotografía privada de la evaluación';image.style.maxWidth='300px';image.src=objectUrl;image.onload=()=>URL.revokeObjectURL(objectUrl);target.append(image);
      }));
      if(!photos.items.length)message('Este expediente no tiene fotografías adjuntas.');
    });
    if(user.roles.some(r=>['patient','evaluator'].includes(r))){
      const form=document.createElement('form');
      form.innerHTML='<h3>Adjuntar fotografía privada</h3><label>ID de evaluación <input name="scan" required></label><label>Fotografía <input name="image" type="file" accept="image/jpeg,image/png,image/webp" required></label><label><input name="consent" type="checkbox" required value="true">Autorizo almacenar esta fotografía en mi expediente privado</label><button>Guardar fotografía</button>';
      form.onsubmit=action(async e=>{const data=new FormData(e.target);const sid=data.get('scan');data.delete('scan');const response=await fetch(`${base}/api/v1/accounts/patients/${pid}/scans/${encodeURIComponent(sid)}/photo`,{method:'POST',body:data});if(!response.ok){const error=await response.json();throw Error(error.error?.message||error.detail||'No se pudo guardar la fotografía');}message('Fotografía guardada en almacenamiento privado.');});
      target.append(form);
    }
  };
  const nav=document.querySelector('nav');if(nav){const link=document.createElement('a');link.href='#accounts';link.textContent='Mi cuenta';nav.append(link);}
  const recovery=document.createElement('form');
  recovery.innerHTML='<h3>Recuperar contraseña</h3><label>Correo <input name="email" type="email" required autocomplete="email"></label><button>Enviar enlace de recuperación</button>';
  $('#account-login').insertAdjacentElement('afterend',recovery);
  recovery.onsubmit=action(async e=>{const data=await api('/password-recovery',Object.fromEntries(new FormData(e.target)),'POST');message(data.message);});
  const reset=document.createElement('form');
  reset.hidden=true;
  reset.innerHTML='<h3>Elegir nueva contraseña</h3><label>Nueva contraseña <input name="password" type="password" minlength="12" maxlength="256" required autocomplete="new-password"></label><button>Actualizar contraseña</button>';
  recovery.insertAdjacentElement('afterend',reset);
  let resetToken=location.hash.startsWith('#reset=')?location.hash.slice(7):'';
  if(resetToken){history.replaceState(null,'',location.pathname+location.search+'#/reset-password');reset.hidden=false;}
  reset.onsubmit=action(async e=>{const data=await api('/password-reset',{token:resetToken,password:new FormData(e.target).get('password')},'POST');resetToken='';token='';selected='';sessionStorage.removeItem('evamcare-account');reset.reset();reset.hidden=true;message(data.message);});
  recovery.id='account-recovery';reset.id='account-reset';
  window.evamcareAccess={api,refresh,recoveryToken:resetToken,openRecord:pid=>openRecord(pid),getUser:()=>user,setPatient:pid=>{selected=pid;window.dispatchEvent(new Event('evamcare-patient-context'));},resetPassword:async(secret,password)=>{await api('/password-reset',{token:secret,password},'POST');token='';selected='';sessionStorage.removeItem('evamcare-account');}};
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
