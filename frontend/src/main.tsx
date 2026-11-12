import { createRoot } from 'react-dom/client';
import { App } from './App';
import '@fontsource-variable/inter/wght.css';
import './styles.css';
import { consumeVerificationLink } from './registration';

const verification = consumeVerificationLink();
createRoot(document.getElementById('root')!).render(<App initialVerification={verification} />);
