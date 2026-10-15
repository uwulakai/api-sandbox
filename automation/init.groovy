import hudson.model.ParametersDefinitionProperty
import hudson.model.StringParameterDefinition
import hudson.model.ChoiceParameterDefinition
import hudson.model.User
import hudson.security.HudsonPrivateSecurityRealm
import hudson.security.FullControlOnceLoggedInAuthorizationStrategy
import hudson.tasks.LogRotator
import hudson.triggers.TimerTrigger
import jenkins.model.BuildDiscarderProperty
import jenkins.model.Jenkins
import jenkins.install.InstallState
import org.jenkinsci.plugins.workflow.job.WorkflowJob
import org.jenkinsci.plugins.workflow.job.properties.DisableConcurrentBuildsJobProperty
import org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition

def server = Jenkins.get()
def env = System.getenv()
def realm = server.getSecurityRealm()
if (!(realm instanceof HudsonPrivateSecurityRealm)) {
    realm = new HudsonPrivateSecurityRealm(false)
    server.setSecurityRealm(realm)
}
// The volume retains the account. Password changes afterwards are made in Jenkins.
if (User.getById(env.JENKINS_ADMIN_USER, false) == null) {
    realm.createAccount(env.JENKINS_ADMIN_USER, env.JENKINS_ADMIN_PASSWORD)
}
def authorization = new FullControlOnceLoggedInAuthorizationStrategy()
authorization.setAllowAnonymousRead(false)
server.setAuthorizationStrategy(authorization)
server.setNumExecutors(1)
server.setSlaveAgentPort(-1)
server.setInstallState(InstallState.INITIAL_SETUP_COMPLETED)

// This dedicated instance runs only our bundled, trusted HTTP suite; no Docker socket.
def job = server.getItem('api-sandbox-e2e')
if (job == null) {
    job = server.createProject(WorkflowJob, 'api-sandbox-e2e')
}
job.setDescription('Real HTTP tests of API Sandbox. Full creates test accounts and disposable mocks; smoke is read-only.')
job.setDefinition(new CpsFlowDefinition(new File('/opt/automation/Jenkinsfile').text, true))
job.addProperty(new ParametersDefinitionProperty(
    new StringParameterDefinition('API_BASE_URL', env.API_BASE_URL, 'API origin, without /api/v1'),
    new StringParameterDefinition('E2E_WAIT_SECONDS', env.E2E_WAIT_SECONDS ?: '90', 'Runtime readiness timeout'),
    new ChoiceParameterDefinition('SUITE', ['full', 'smoke'] as String[], 'Full scenarios or read-only availability checks')
))
job.addProperty(new DisableConcurrentBuildsJobProperty())
job.addProperty(new BuildDiscarderProperty(new LogRotator(-1, 30, -1, 30)))
job.setTriggers(env.E2E_CRON?.trim() ? [new TimerTrigger(env.E2E_CRON.trim())] : [])
job.save()
server.save()
