import { Route, Routes } from "react-router-dom";
import Home from "./pages/Home";
import Game from "./pages/Game";
import MemoryBrowserPage from "./pages/MemoryBrowserPage";
import SystemPage from "./pages/SystemPage";
import BatchExperimentsPage from "./pages/BatchExperimentsPage";
import ExpertReviewPage from "./pages/ExpertReviewPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/system" element={<SystemPage />} />
      <Route path="/batch-experiments" element={<BatchExperimentsPage />} />
      <Route path="/expert-review/:batchUuid" element={<ExpertReviewPage />} />
      <Route path="/play/:scenarioId" element={<Game />} />
      <Route path="/memory/:sessionUuid" element={<MemoryBrowserPage />} />
    </Routes>
  );
}
