import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CatalogProvider } from './context/CatalogContext';
import Header from './components/Header';
import Footer from './components/Footer';
import CatalogPage from './pages/CatalogPage';
import DetailPage from './pages/DetailPage';
import FeedbackPage from './pages/FeedbackPage';
import RepoFeedbackPage from './pages/RepoFeedbackPage';
import BenchmarksPage from './pages/BenchmarksPage';

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <CatalogProvider>
        <BrowserRouter>
          <Header />
          <Routes>
            <Route path="/" element={<CatalogPage />} />
            <Route path="/feedback" element={<FeedbackPage />} />
            <Route path="/repo-feedback" element={<RepoFeedbackPage />} />
            <Route path="/benchmarks" element={<BenchmarksPage />} />
            <Route path="/:type/:name" element={<DetailPage />} />
          </Routes>
          <Footer />
        </BrowserRouter>
      </CatalogProvider>
    </QueryClientProvider>
  );
}
