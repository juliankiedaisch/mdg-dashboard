import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import api from './utils/api';
import { UserProvider } from './contexts/UserContext';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout/Layout';
import Dashboard from './pages/Dashboard/Dashboard';
import NotAllowed from './pages/NotAllowed';
import Login from './pages/Login';
import UnifyDashboard from './pages/Unify/UnifyDashboard';
import DeviceGroupDetail from './pages/Unify/DeviceGroupDetail';
import CSVGeneratorDashboard from './pages/CSVGenerator/CSVGeneratorDashboard';
import ApprovalsDashboard from './pages/Approvals/ApprovalsDashboard';
import ApplicationView from './pages/Approvals/ApplicationView';
import TeacherTools from './pages/TeacherTools/TeacherTools';
import SurveyLanding from './pages/Surveys/SurveyLanding';
import SurveyTypeSelector from './pages/Surveys/SurveyTypeSelector';
// Normal survey pages
import NewSurvey from './pages/Surveys/normal/pages/NewSurvey';
import EditSurvey from './pages/Surveys/normal/pages/EditSurvey';
import SurveyDetail from './pages/Surveys/normal/pages/SurveyDetail';
import SurveyParticipate from './pages/Surveys/normal/pages/SurveyParticipate';
// Special survey pages
import NewSpecialSurvey from './pages/Surveys/special/pages/NewSpecialSurvey';
import NewEvaluationTemplate from './pages/Surveys/special/pages/NewEvaluationTemplate';
import SpecialSurveyDetail from './pages/Surveys/special/pages/SpecialSurveyDetail';
import SpecialSurveyPhase1 from './pages/Surveys/special/pages/SpecialSurveyPhase1';
import SpecialSurveyPhase2 from './pages/Surveys/special/pages/SpecialSurveyPhase2';
import SpecialSurveyPhase3 from './pages/Surveys/special/pages/SpecialSurveyPhase3';
import WordCloudList from './pages/WordCloud/WordCloudList';
import NewWordCloud from './pages/WordCloud/NewWordCloud';
import WordCloudDetail from './pages/WordCloud/WordCloudDetail';
import WordCloudParticipate from './pages/WordCloud/WordCloudParticipate';
import PermissionManagement from './pages/PermissionManagement/PermissionManagement';
import AssistantChatPage from './pages/Assistant/AssistantChatPage';
import AssistantAdminPage from './pages/Assistant/AssistantAdminPage';
import './App.css';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState(null);

  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      const response = await api.get('/api/auth/status');
      if (response.data.authenticated) {
        setIsAuthenticated(true);
        setUser({
          username: response.data.username,
          permissions: response.data.permissions || [],
          is_super_admin: response.data.is_super_admin || false
        });
      } else {
        setIsAuthenticated(false);
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return <div className="loading">Loading...</div>;
  }

  return (
    <Router>
      <UserProvider user={user}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/not-allowed" element={<NotAllowed />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute isAuthenticated={isAuthenticated} isLoading={isLoading}>
                <Layout>
                  <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/dashboard" element={<Dashboard />} />
                    <Route path="/unify" element={<UnifyDashboard />} />
                    <Route path="/unify/device-groups/:groupId" element={<DeviceGroupDetail />} />
                    <Route path="/csvgenerator" element={<CSVGeneratorDashboard />} />
                    <Route path="/approvals" element={<ApprovalsDashboard />} />
                    <Route path="/approvals/:appId" element={<ApplicationView />} />
                    <Route path="/teachertools" element={<TeacherTools />} />
                    <Route path="/teachertools/wordcloud" element={<WordCloudList />} />
                    <Route path="/teachertools/wordcloud/new" element={<NewWordCloud />} />
                    <Route path="/teachertools/wordcloud/join/:accessCode" element={<WordCloudParticipate />} />
                    <Route path="/teachertools/wordcloud/:wcId" element={<WordCloudDetail />} />
                    <Route path="/surveys" element={<SurveyLanding />} />
                    <Route path="/surveys/my" element={<SurveyLanding />} />
                    <Route path="/surveys/new" element={<SurveyTypeSelector />} />
                    <Route path="/surveys/new/normal" element={<NewSurvey />} />
                    <Route path="/surveys/new/special" element={<NewSpecialSurvey />} />
                    <Route path="/surveys/new/evaluation-template" element={<NewEvaluationTemplate />} />
                    <Route path="/surveys/evaluation-template/:surveyId" element={<NewEvaluationTemplate />} />
                    <Route path="/surveys/special/:ssId" element={<SpecialSurveyDetail />} />
                    <Route path="/surveys/special/:ssId/phase1" element={<SpecialSurveyPhase1 />} />
                    <Route path="/surveys/special/:ssId/phase2" element={<SpecialSurveyPhase2 />} />
                    <Route path="/surveys/special/:ssId/phase3" element={<SpecialSurveyPhase3 />} />
                    <Route path="/surveys/:surveyId" element={<SurveyDetail />} />
                    <Route path="/surveys/:surveyId/edit" element={<EditSurvey />} />
                    <Route path="/surveys/:surveyId/participate" element={<SurveyParticipate />} />
                    <Route path="/permissions" element={<PermissionManagement />} />
                    <Route path="/assistant" element={<AssistantChatPage />} />
                    <Route path="/assistant/admin" element={<AssistantAdminPage />} />
                  </Routes>
                </Layout>
              </ProtectedRoute>
            }
          />
        </Routes>
      </UserProvider>
    </Router>
  );
}

export default App;
