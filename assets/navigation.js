/* Static-host compatible routing. The server remains the authorization boundary. */
(() => {
  const access=window.evamcareAccess;
  const account=document.querySelector('#accounts');
  const labels={admin:'Administrador',evaluator:'Evaluador',patient:'Paciente',professional:'Profesional'};
  let user, role='', secret=access.recoveryToken||'', renderVersion=0;
  const authRoutes=['/login','/activate-account','/forgot-password','/reset-password'];
  const shell=document.createElement('section');shell.className='section access-shell';
  shell.innerHTML='<aside id="role-navigation" aria-label="Navegación del panel"></aside><div id="access-heading"><h1></h1><p role="status" id="route-status"></p></div>';
  account.before(shell);
  const css=document.createElement('style');css.textContent=`[hidden]{display:none!important}.access-shell{display:grid;grid-template-columns:220px 1fr;gap:24px}.access-shell aside{display:flex;flex-direction:column;gap:12px}.access-shell a{color:inherit}.access-auth{max-width:560px;margin:32px auto}.access-auth form{display:grid;gap:18px}.access-auth input{width:100%}.access-auth label{display:grid;gap:8px}#accounts pre{background:#faf5ef;padding:20px;border-radius:16px}#account-portal{display:grid;gap:24px}@media(max-width:700px){.access-shell{grid-template-columns:1fr}.access-shell aside{flex-direction:row;flex-wrap:wrap}}`;
  document.head.append(css);
  const go=path=>{location.hash='#'+path;};
  const link=(parent,text,path)=>{const a=document.createElement('a');a.textContent=text;a.href='#'+path;parent.append(a);return a;};
  const status=text=>{document.querySelector('#route-status').textContent=text;};
  const login=document.querySelector('#account-login');
  const activate=document.querySelector('#account-activate');
  const recovery=document.querySelector('#account-recovery');
  const reset=document.querySelector('#account-reset');
  activate.querySelector('[name=token]').closest('label').hidden=true;
  for(const form of [activate,reset]){
    const label=document.createElement('label');label.textContent='Confirmar contraseña';
    const input=document.createElement('input');input.name='confirmation';input.type='password';input.required=true;input.autocomplete='new-password';label.append(input);form.querySelector('button').before(label);
  }
  const authLinks=document.createElement('div');authLinks.id='auth-links';account.append(authLinks);
  link(authLinks,'¿Olvidaste tu contraseña?','/forgot-password');authLinks.append(document.createElement('br'));
  link(authLinks,'¿Tienes una invitación? Activa tu cuenta.','/activate-account');
  activate.onsubmit=async e=>{e.preventDefault();try{const d=new FormData(activate);if(d.get('password')!==d.get('confirmation'))throw Error('Las contraseñas no coinciden.');await access.api('/activate',{token:secret,password:d.get('password')},'POST');secret='';activate.reset();go('/login');}catch(error){status(error.message);}};
  reset.onsubmit=async e=>{e.preventDefault();try{const d=new FormData(reset);if(d.get('password')!==d.get('confirmation'))throw Error('Las contraseñas no coinciden.');await access.resetPassword(secret,d.get('password'));secret='';reset.reset();user=null;go('/login');}catch(error){status(error.message);}};
  const nav=document.querySelector('.topbar nav');nav.replaceChildren();
  const entry=link(nav,'Iniciar sesión','/login');
  document.querySelector('.brand').href='#/';
  const logout=document.querySelector('#account-logout');
  const originalLogout=logout.onclick;
  logout.onclick=async e=>{await originalLogout(e);};
  function chooseRole(){
    const target=document.querySelector('#role-navigation');target.replaceChildren();
    user.roles.filter(r=>labels[r]).forEach(r=>link(target,labels[r],'/'+r+'/dashboard'));
    status('Selecciona la función en la que deseas trabajar.');
  }
  async function render(){
    const version=++renderVersion;
    const raw=location.hash.slice(1)||'/';const [path,query='']=raw.split('?');
    const params=new URLSearchParams(query);
    if(params.has('token')){secret=params.get('token');history.replaceState(null,'',location.pathname+location.search+'#'+path);}
    const route=path.startsWith('/')?path:'/';
    const auth=authRoutes.includes(route), publicHome=route==='/';
    role=route.split('/')[1];
    for(const node of document.querySelectorAll('main > section'))node.hidden=true;
    // Existing scanner is a dialog and is preserved unchanged.
    if(publicHome){for(const id of ['inicio','como-funciona','privacidad'])document.getElementById(id).hidden=false;document.querySelector('.trust-strip').hidden=false;}
    shell.hidden=publicHome;account.hidden=publicHome;
    account.classList.toggle('access-auth',auth);
    account.querySelector('h2').hidden=auth;
    if(auth)document.querySelector('#account-message').replaceChildren();
    for(const form of [login,activate,recovery,reset])form.hidden=true;
    document.querySelector('#account-portal').hidden=true;authLinks.hidden=route!='/login';
    document.querySelector('#role-navigation').hidden=auth;
    const heading=shell.querySelector('h1');status('');
    entry.textContent=user?'Ir a mi panel':'Iniciar sesión';entry.href=user?'#/panel':'#/login';
    document.querySelector('.topbar [data-start-scan]').hidden=!publicHome;
    if(auth){
      heading.textContent={'/login':'Iniciar sesión','/activate-account':'Activar cuenta','/forgot-password':'Recuperar contraseña','/reset-password':'Nueva contraseña'}[route];
      const form={'/login':login,'/activate-account':activate,'/forgot-password':recovery,'/reset-password':reset}[route];form.hidden=false;
      if(['/activate-account','/reset-password'].includes(route)&&!secret){form.hidden=true;status('Abre el enlace recibido. Si ha vencido, solicita uno nuevo a quien te invitó o recupera tu contraseña.');link(document.querySelector('#route-status'),' Recuperar acceso','/forgot-password');}
      if(route==='/activate-account'&&secret){try{const invited=await access.api('/invitation-check',{token:secret},'POST');status('Bienvenido/a, '+invited.name);}catch(error){form.hidden=true;status(error.message);}}
      return;
    }
    if(publicHome)return;
    try{user=await access.api('/me');}catch(error){user=null;go('/login');return;}
    if(version!==renderVersion)return;
    if(route==='/panel'){if(user.roles.length===1){go('/'+user.roles[0]+'/dashboard');return;}heading.textContent='Elige tu panel';chooseRole();return;}
    if(!user.roles.includes(role)){heading.textContent='Acceso no autorizado';status('Tu cuenta no tiene permiso para este panel.');chooseRole();return;}
    heading.textContent='Panel de '+labels[role];
    const menu=document.querySelector('#role-navigation');menu.replaceChildren();
    const sections={admin:[['Inicio','dashboard'],['Gestión de usuarios','users'],['Pacientes','patients'],['Evaluadores','evaluators'],['Profesionales','professionals'],['Evaluaciones','evaluations'],['Configuración','settings']],evaluator:[['Inicio','dashboard'],['Pacientes autorizados','patients'],['Crear nuevo paciente','new-patient'],['Ficha e historial','record']],patient:[['Mi perfil y mi piel','dashboard'],['Mi historial y evolución','record'],['Compartir expediente','sharing'],['Profesionales autorizados','grants']],professional:[['Inicio','dashboard'],['Pacientes compartidos conmigo','grants'],['Expedientes y evolución','record'],['Notas y seguimientos','record']]};
    sections[role].forEach(([text,id])=>link(menu,text,'/'+role+'/'+id));
    if(user.roles.length>1)link(menu,'Cambiar rol','/panel');link(menu,'Mi cuenta','/'+role+'/settings');
    menu.append(logout);
    const page=route.split('/')[2]||'dashboard';
    const visible=new Set();
    if(role==='admin'){if(['dashboard','users','evaluators','professionals'].includes(page))visible.add('account-admin');if(['dashboard','patients'].includes(page))visible.add('account-directory');if(page==='users')visible.add('account-invite');}
    if(role==='evaluator'){if(['dashboard','patients'].includes(page))visible.add('account-directory');if(page==='new-patient')visible.add('account-invite');}
    if(role==='patient'){if(['dashboard','record'].includes(page))visible.add('account-record');if(page==='sharing')visible.add('account-sharing');if(['sharing','grants'].includes(page))visible.add('account-grants');}
    if(role==='professional'){if(['dashboard','grants'].includes(page))visible.add('account-grants');if(page==='record')visible.add('account-record');}
    if(page==='record'&&role==='evaluator')visible.add('account-record');
    document.querySelector('#account-portal').hidden=false;
    for(const id of ['account-admin','account-directory','account-invite','account-sharing','account-grants','account-record'])document.getElementById(id).hidden=!visible.has(id);
    if(page==='settings')status(user.name+' · '+user.email);
    if(role==='admin'&&page==='evaluations')status('El rol administrador gestiona cuentas; los expedientes clínicos requieren asignación como evaluador.');
    if(visible.has('account-directory'))document.querySelector('#patients-load').click();
    if(role==='admin'&&visible.has('account-admin')){document.querySelector('#user-role').value=page==='evaluators'?'evaluator':page==='professionals'?'professional':'';document.querySelector('#users-load').click();}
  }
  window.addEventListener('evamcare-auth',e=>{user=e.detail;if(location.hash==='#/login'||!location.hash)go('/panel');else render();});
  window.addEventListener('hashchange',render);
  document.querySelector('#patients-list').addEventListener('click',e=>{if(e.target.textContent==='Ver expediente')go('/'+role+'/record');});
  document.querySelector('#grants-list').addEventListener('click',e=>{if(e.target.textContent==='Ver expediente')go('/professional/record');});
  if(location.hash.startsWith('#reset=')){secret=location.hash.slice(7);history.replaceState(null,'',location.pathname+location.search+'#/reset-password');}
  render();
})();
