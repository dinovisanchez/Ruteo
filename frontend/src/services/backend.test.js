import { avisoSinBackend } from './backend';

test('en el Mac pide correr ./iniciar.sh', () => {
  expect(avisoSinBackend('http://localhost:8000/api', 'http://localhost:3000')).toContain('./iniciar.sh');
});

test('en Vercel apuntando a localhost pide REACT_APP_API_URL', () => {
  const aviso = avisoSinBackend('http://localhost:8000/api', 'https://ruteo.vercel.app');
  expect(aviso).toContain('REACT_APP_API_URL');
  expect(aviso).not.toContain('./iniciar.sh');
});

test('con un servidor que no responde pide revisarlo y FRONTEND_URL', () => {
  const aviso = avisoSinBackend('https://ruteo-api.example/api', 'https://ruteo.vercel.app');
  expect(aviso).toContain('https://ruteo-api.example/api');
  expect(aviso).toContain('FRONTEND_URL');
});
