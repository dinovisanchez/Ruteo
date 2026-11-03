import React, {
  createContext, useCallback, useContext, useEffect, useRef, useState,
} from 'react';
import { Spin } from 'antd';
import { getAuthConfig } from '../services/api';
import {
  alVencerSesion, cerrarSesion, iniciarSesion, sesionActual,
} from '../services/sesion';

const SesionContext = createContext({ cuenta: null, salir: null });
// The account signed in (null on each coordinator's Mac, where there is no login)
export const useSesion = () => useContext(SesionContext);

const SCRIPT_GOOGLE = 'https://accounts.google.com/gsi/client';

const cargarGoogle = () => new Promise((listo, falla) => {
  if (window.google?.accounts?.id) {
    listo(window.google);
    return;
  }
  const script = document.createElement('script');
  script.src = SCRIPT_GOOGLE;
  script.async = true;
  script.onload = () => listo(window.google);
  script.onerror = () => falla(new Error('No se pudo cargar «Iniciar sesión con Google»'));
  document.head.appendChild(script);
});

const Login = ({ clientId, dominios, onCuenta, aviso }) => {
  const boton = useRef(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    let vivo = true;
    cargarGoogle()
      .then((google) => {
        if (!vivo) return;
        google.accounts.id.initialize({
          client_id: clientId,
          // Only shows the accounts of the company in Google's list
          hd: dominios.length === 1 ? dominios[0] : undefined,
          auto_select: true,
          callback: ({ credential }) => onCuenta(iniciarSesion(credential)),
        });
        google.accounts.id.renderButton(boton.current, {
          theme: 'outline', size: 'large', text: 'signin_with', shape: 'pill', locale: 'es',
        });
        google.accounts.id.prompt();
      })
      .catch((e) => setError(e.message));
    return () => { vivo = false; };
  }, [clientId, dominios, onCuenta]);
  return (
    <div className="login">
      <div className="login-card">
        <img src={`${process.env.PUBLIC_URL}/bolt.png`} alt="" className="login-icon" />
        <div className="login-title">Ruteo</div>
        <div className="muted-text">
          Entra con tu cuenta de Google de {dominios.join(' o ') || 'la empresa'}
        </div>
        <div ref={boton} className="login-button" />
        {aviso && <div className="warn-text">{aviso}</div>}
        {error && <div className="warn-text">{error}</div>}
      </div>
    </div>
  );
};

/**
 * On a shared server (the backend has GOOGLE_CLIENT_ID), asks for the Bia Google account before
 * showing the app and again when the session expires. Without it, shows the app as always.
 */
const Acceso = ({ children }) => {
  const [config, setConfig] = useState(undefined);
  const [cuenta, setCuenta] = useState(sesionActual);
  const [aviso, setAviso] = useState(null);

  useEffect(() => {
    // Without a backend the app opens as always and says the backend is not running
    getAuthConfig()
      .then((c) => setConfig(c.google_client_id ? c : null))
      .catch(() => setConfig(null));
  }, []);
  useEffect(() => {
    alVencerSesion(() => {
      cerrarSesion();
      setCuenta(null);
      setAviso('La sesión venció o esa cuenta no puede entrar: vuelve a iniciar sesión');
    });
  }, []);
  const salir = useCallback(() => {
    cerrarSesion();
    window.google?.accounts?.id?.disableAutoSelect();
    setAviso(null);
    setCuenta(null);
  }, []);
  const alEntrar = useCallback((nueva) => {
    setAviso(null);
    setCuenta(nueva);
  }, []);

  if (config === undefined) {
    return <div className="login"><Spin /></div>;
  }
  if (config && !cuenta) {
    return <Login clientId={config.google_client_id} dominios={config.dominios} onCuenta={alEntrar} aviso={aviso} />;
  }
  return (
    <SesionContext.Provider value={{ cuenta: config ? cuenta : null, salir: config ? salir : null }}>
      {children}
    </SesionContext.Provider>
  );
};

export default Acceso;
