import {
  cerrarSesion, iniciarSesion, leerToken, sesionActual,
} from './sesion';

// A token like Google's: header.payload.signature, with base64url and accents in the name
const base64url = (texto) => btoa(unescape(encodeURIComponent(texto))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const token = (datos) => `${base64url('{"alg":"RS256"}')}.${base64url(JSON.stringify(datos))}.firma`;

test('lee la cuenta y cuándo vence el token', () => {
  const vence = Math.floor(Date.now() / 1000) + 3600;
  expect(leerToken(token({ name: 'Ana Pérez', email: 'ana@bia.app', exp: vence }))).toEqual({
    token: expect.any(String), nombre: 'Ana Pérez', correo: 'ana@bia.app', vence: vence * 1000,
  });
  expect(leerToken('no-es-un-token')).toBeNull();
});

test('una sesión vencida no cuenta y cerrar sesión la borra', () => {
  iniciarSesion(token({ email: 'ana@bia.app', exp: Math.floor(Date.now() / 1000) - 10 }));
  expect(sesionActual()).toBeNull();
  iniciarSesion(token({ email: 'ana@bia.app', exp: Math.floor(Date.now() / 1000) + 600 }));
  expect(sesionActual().correo).toBe('ana@bia.app');
  expect(JSON.parse(sessionStorage.getItem('ruteo_sesion')).correo).toBe('ana@bia.app');
  cerrarSesion();
  expect(sesionActual()).toBeNull();
  expect(sessionStorage.getItem('ruteo_sesion')).toBeNull();
});
