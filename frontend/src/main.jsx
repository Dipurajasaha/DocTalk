import './styles/fonts.css';
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import { SessionProvider } from './contexts/SessionContext';
import { AppProviders } from './contexts';

ReactDOM.createRoot(document.getElementById('root')).render(
	<React.StrictMode>
		<AppProviders>
			<SessionProvider>
				<App />
			</SessionProvider>
		</AppProviders>
	</React.StrictMode>
);