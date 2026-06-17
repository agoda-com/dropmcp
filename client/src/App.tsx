import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { CatalogProvider } from './context/CatalogContext';
import Header from './components/Header';
import Footer from './components/Footer';
import CatalogPage from './pages/CatalogPage';
import DetailPage from './pages/DetailPage';
import FeedbackPage from './pages/FeedbackPage';

export default function App() {
  return (
    <CatalogProvider>
      <BrowserRouter>
        <Header />
        <Routes>
          <Route path="/" element={<CatalogPage />} />
          <Route path="/feedback" element={<FeedbackPage />} />
          <Route path="/:type/:name" element={<DetailPage />} />
        </Routes>
        <Footer />
      </BrowserRouter>
    </CatalogProvider>
  );
}
