import { createBrowserRouter } from "react-router-dom";
import AppLayout from "./layouts/AppLayout";
import DashboardPage from "./pages/DashboardPage";
import ProvidersPage from "./pages/ProvidersPage";
import TopicsPage from "./pages/TopicsPage";
import TopicDetailPage from "./pages/TopicDetailPage";
import TopicChatPage from "./pages/TopicChatPage";
import NotFoundPage from "./pages/NotFoundPage";

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: "/", element: <DashboardPage /> },
      { path: "/providers", element: <ProvidersPage /> },
      { path: "/topics", element: <TopicsPage /> },
      { path: "/topics/:topicId", element: <TopicDetailPage /> },
      { path: "/topics/:topicId/chat", element: <TopicChatPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
