import { createBrowserRouter, Navigate } from 'react-router'

import { Layout } from './components/Layout'
import { GuestRoute, ProtectedRoute } from './components/RouteGuards'
import { DashboardPage } from './pages/DashboardPage'
import { FundDetailPage } from './pages/FundDetailPage'
import { FundsPage } from './pages/FundsPage'
import { GoalSimulationPage } from './pages/GoalSimulationPage'
import { GoalsPage } from './pages/GoalsPage'
import { LoginPage } from './pages/LoginPage'
import { ProfilePage } from './pages/ProfilePage'
import { RegisterPage } from './pages/RegisterPage'
import { RetirementPage } from './pages/RetirementPage'
import { RiskQuestionnairePage } from './pages/RiskQuestionnairePage'
import { RiskResultPage } from './pages/RiskResultPage'
import { StatusPage } from './pages/StatusPage'

export const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <Navigate to="/dashboard" replace /> },
      { path: '/status', element: <StatusPage /> },
      {
        element: <GuestRoute />,
        children: [
          { path: '/login', element: <LoginPage /> },
          { path: '/register', element: <RegisterPage /> },
        ],
      },
      {
        element: <ProtectedRoute />,
        children: [
          { path: '/dashboard', element: <DashboardPage /> },
          { path: '/profile', element: <ProfilePage /> },
          { path: '/risk', element: <RiskResultPage /> },
          { path: '/risk/questionnaire', element: <RiskQuestionnairePage /> },
          { path: '/goals', element: <GoalsPage /> },
          { path: '/goals/:goalId/simulate', element: <GoalSimulationPage /> },
          { path: '/retirement', element: <RetirementPage /> },
          { path: '/funds', element: <FundsPage /> },
          { path: '/funds/:fundId', element: <FundDetailPage /> },
        ],
      },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])
