/**
 * Session when Ruteo runs on a shared server (see components/Acceso): the Google ID token, or the
 * token the server gives for the access key. It lives in sessionStorage until it expires or the
 * person signs out.
 */
const SESION_KEY = 'ruteo_sesion';
let sesion = null;
try {
  sesion = JSON.parse(sessionStorage.getItem(SESION_KEY) || 'null');
} catch (error) {
  sesion = null;
}
let alVencer = () => {};
export const avisarSesionVencida = () => alVencer();

// The account inside a Google ID token (a JWT): name, email and when it expires
export const leerToken = (token) => {
  try {
    const base = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    // atob gives bytes; the percent-encoding turns them back into UTF-8 text (names with accents)
    const texto = decodeURIComponent(atob(base).split('').map((c) => `%${c.charCodeAt(0).toString(16).padStart(2, '0')}`).join(''));
    const datos = JSON.parse(texto);
    return { token, nombre: datos.name || datos.email, correo: datos.email, vence: datos.exp * 1000 };
  } catch (error) {
    return null;
  }
};
export const sesionActual = () => (sesion && sesion.vence > Date.now() ? sesion : null);
export const iniciarSesion = (token) => {
  sesion = leerToken(token);
  try {
    if (sesion) sessionStorage.setItem(SESION_KEY, JSON.stringify(sesion));
  } catch (error) {
    // Without storage the session lasts until the page is reloaded
  }
  return sesion;
};
export const cerrarSesion = () => {
  sesion = null;
  try {
    sessionStorage.removeItem(SESION_KEY);
  } catch (error) {
    // Nothing stored
  }
};
// What to do when the server says the session is over (401): show the login again
export const alVencerSesion = (accion) => { alVencer = accion; };
