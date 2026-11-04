/**
 * What to tell the person when the backend does not answer, depending on where the app is open:
 * on the coordinator's Mac (start ./iniciar.sh), on a server like Vercel still pointing at
 * localhost (REACT_APP_API_URL is missing), or pointing at a server that does not answer.
 */
export const avisoSinBackend = (apiUrl, origen) => {
  const local = (url) => /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?(\/|$)/.test(url);
  if (local(apiUrl) && local(origen)) {
    return 'El backend no está corriendo en http://localhost:8000. Ciérralo todo y ejecuta ./iniciar.sh; '
      + 'si falla, revisa logs/backend-8000.log.';
  }
  if (local(apiUrl)) {
    return `Esta página (${origen}) busca el backend en ${apiUrl}, que solo existe en el computador de cada `
      + 'coordinador. Pon el backend en un servidor y, en Vercel (Settings → Environment Variables), agrega '
      + 'REACT_APP_API_URL con su dirección terminada en /api; luego vuelve a desplegar (Redeploy).';
  }
  return `El backend en ${apiUrl} no responde o no deja entrar a esta página. Revisa que el servidor esté `
    + `encendido y que su variable FRONTEND_URL tenga ${origen}.`;
};
