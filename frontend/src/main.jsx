import './styles/fonts.css';
import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';

function Root() {
	const [session, setSession] = useState(null);
	const [loaded, setLoaded] = useState(false);

	useEffect(() => {
		// Quick bootstrap: avoid noisy proxy errors when backend is down by
		// probing backend health first with a short timeout. If health fails,
		// skip session verification so dev server doesn't flood logs.
		const local = localStorage.getItem('doctalk_session');
		const parsed = local ? JSON.parse(local) : null;
		const token = localStorage.getItem('doctalk_token');

		const timeoutFetch = async (url, opts = {}, ms = 1500) => {
			const controller = new AbortController();
			const id = setTimeout(() => controller.abort(), ms);
			try {
				const res = await fetch(url, { ...opts, signal: controller.signal });
				clearTimeout(id);
				return res;
			} catch (e) {
				clearTimeout(id);
				throw e;
			}
		};

		const verify = async () => {
			try {
				// probe health endpoint first
				try {
					const h = await timeoutFetch('/health', { credentials: 'include' }, 1200);
					if (!h.ok) throw new Error('unhealthy');
				} catch (err) {
					// backend appears down or slow; skip session checks to avoid ECONNREFUSED spam
					setLoaded(true);
					return;
				}

				// If health is OK, perform the lightweight session check using bearer token (/me)
				if (token) {
					try {
						const res = await fetch('/me', { headers: { Authorization: `Bearer ${token}` } });
						if (res.ok) {
							const data = await res.json();
							// data should contain profile info; backend uses role in token, but include it here if present
							const role = data.role || (parsed && parsed.role) || null;
							const sess = { ...(data || {}), role, token };
							setSession(sess);
							setLoaded(true);
							// persist lightweight session hint
							try { localStorage.setItem('doctalk_session', JSON.stringify({ role })); } catch (e) {}
							return;
						}
					} catch (e) {
						// token invalid or network error; continue to clear
					}
				}

			} catch (err) {
				// ignore network errors for bootstrap
			}
			// no session
			localStorage.removeItem('doctalk_session');
			setSession(null);
			setLoaded(true);
		};

		verify();
	}, []);

	if (!loaded) return null; // avoid rendering until bootstrap completes

	return <App initialSession={session} setSession={setSession} />;
}

ReactDOM.createRoot(document.getElementById('root')).render(
	<React.StrictMode>
		<Root />
	</React.StrictMode>
);