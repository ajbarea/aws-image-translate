// Authentication helper functions
class AuthManager {
  constructor(config) {
    this.config = config;
    this.cognitoUser = null;
    this.setupCognito();
  }

  setupCognito() {
    const poolData = {
      UserPoolId: this.config.userPoolId,
      ClientId: this.config.userPoolWebClientId,
    };
    this.userPool = new AmazonCognitoIdentity.CognitoUserPool(poolData);
  }

  async signIn(username, password) {
    return new Promise((resolve, reject) => {
      const authData = {
        Username: username,
        Password: password,
      };

      const authDetails = new AmazonCognitoIdentity.AuthenticationDetails(
        authData
      );
      const userData = {
        Username: username,
        Pool: this.userPool,
      };

      this.cognitoUser = new AmazonCognitoIdentity.CognitoUser(userData);
      this.cognitoUser.authenticateUser(authDetails, {
        onSuccess: (result) => {
          this.setupAWSCredentials(result.getIdToken().getJwtToken());
          resolve(result);
        },
        onFailure: (err) => {
          reject(err);
        },
      });
    });
  }

  async setupAWSCredentials(idToken) {
    const loginKey = `cognito-idp.${this.config.region}.amazonaws.com/${this.config.userPoolId}`;
    AWS.config.credentials = new AWS.CognitoIdentityCredentials({
      IdentityPoolId: this.config.identityPoolId,
      Logins: {
        [loginKey]: idToken,
      },
    });

    // Refresh credentials
    await AWS.config.credentials.getPromise();
  }

  async signOut() {
    if (this.cognitoUser) {
      this.cognitoUser.signOut();
      this.cognitoUser = null;
      AWS.config.credentials.clearCachedId();
    }
  }

  isAuthenticated() {
    const user = this.userPool.getCurrentUser();
    return user !== null;
  }
}

export { AuthManager };
