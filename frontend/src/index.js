import React from 'react';
import ReactDOM from 'react-dom/client';
import { ConfigProvider } from 'antd';
import esES from 'antd/locale/es_ES';
import dayjs from 'dayjs';
import 'dayjs/locale/es';
import './index.css';
import App from './App';
import iosTheme from './theme';

dayjs.locale('es');

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <ConfigProvider theme={iosTheme} locale={esES}>
      <App />
    </ConfigProvider>
  </React.StrictMode>
);
