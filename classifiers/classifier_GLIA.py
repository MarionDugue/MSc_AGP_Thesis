from scipy.stats import multivariate_normal as mvn
import numpy as np
import logging
from sklearn.linear_model import LinearRegression


class classifier_GLIA:

    
    def __init__(self, IA_0=30, override_slopes=False,enable_logging=True):
        self.info = dict()
        self.info['type'] = 'GLIA'
        self.IA_0         = IA_0

        self.logger = logging.getLogger(__name__)
        if enable_logging:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.CRITICAL)
# ---------------- #

    def add_info(self, info_dict):
        """Add info_dict to classifier object info

        Parameters
        ----------
        info_dict: dictionary to update classifier information
        """

        self.info.update(info_dict)

        return

# ---------------- #

    def fit(self, X_train, y_train, IA_train):
        """Fit classifier to input training data X_train with labels y_train and incidence angle IA_train

        Parameters
        ----------
        X_train: training data [N,d]
        y_train: training labels [N,]
        IA_train: training incidence angle [N,1] or [N,]

        Returns
        -------
        self.n_feat : number of features
        self.n_class : number of classes
        self.trained_classes : list of trained classes (in case y_train does not contain all classes indices)
        self.a : slope intercept at IA=0
        self.b : slope covariance matrix for each class [n_class,d,d]
        self.mu : class-dependent mean vector at IA_0 [n_class,d]
        self.Sigma : class-dependent covariance matrix at IA_0 [n_class,d,d]
        self.mvn : class-dependent multivariate normal distribution at IA_0
        """

        self.logger.warning('self.fit() is currently implemented only for balanced training distribution over the full IA range')
        self.logger.warning('Unbalanced training data distribution may result in erroneous slope estiamtes and poor classification results')

        assert len(X_train.shape) == 2, 'X_train must be of shape (N,d)'
    
        assert X_train.shape[0] == IA_train.shape[0], 'X_train and IA_train must have same number of samples'

        assert X_train.shape[0] == y_train.shape[0], 'X_train and y_train must have same number of samples'

        N, self.n_feat = X_train.shape
        self.logger.debug(f'Number of training points: {N}')
        self.logger.debug(f'Number of features: {self.n_feat}')

        unique_classes = np.unique(y_train).astype(int)
        self.n_class = unique_classes.max()
        self.logger.debug(f'Unique class labels in training data: {unique_classes}')
        self.logger.debug(f'Highest class index in training data: {self.n_class}')

        # initialisation
        self.a = np.full([self.n_class, self.n_feat], np.nan)
        self.b = np.full([self.n_class, self.n_feat], np.nan)

        X_projected = np.zeros(X_train.shape)

        for i, cl in enumerate(unique_classes):

            self.logger.debug(f'Processing class {cl}')

            for feat in range(self.n_feat):

                self.logger.debug(f'Estimating a and b for class {cl} and dimension {feat}')

                model = LinearRegression()
                model.fit(np.reshape(IA_train[y_train==cl],(-1,1)), np.reshape(X_train[y_train==cl,feat],(-1,1)))

                # extract intercept and slope
                self.a[cl-1,feat] = model.intercept_[0]
                self.b[cl-1,feat] = model.coef_[0][0]

                # project current dimension of X_train along slope b to IA_0
                X_projected[y_train==cl,feat] = X_train[y_train==cl,feat] - self.b[cl-1,feat] * (IA_train[y_train==cl]-self.IA_0)

        self.logger.debug('Estimated slope and intercept for all classes in training data')
        self.logger.debug('Projected X_train values to IA_0')

        # initialisation
        self.mu    = np.full([self.n_class, self.n_feat], np.nan)
        self.Sigma = np.full([self.n_class, self.n_feat, self.n_feat], np.nan)

        self.class_mvn = dict()

        self.trained_classes = []

        for cl in unique_classes:

            self.logger.debug(f'Estimating mu and Sigma for class {cl}')

            self.trained_classes.append(cl)

            X_cl = X_projected[y_train==cl,:]

            self.logger.debug(f'Number of training points for current class: {X_cl.shape[0]}')
            self.logger.debug(f'Number of dimensions for current class: {X_cl.shape[1]}')

            # estimate mu and Sigma
            self.mu[cl-1,:]      = X_cl.mean(0)
            self.Sigma[cl-1,:,:] = np.cov(np.transpose(X_cl))

            # multivariate_normal
            self.class_mvn[str(cl)] = mvn(self.mu[cl-1,:],self.Sigma[cl-1,:,:])

        return

# ---------------- #

    def predict(self, X_test, IA_test):
        """Predict class labels y_pred for input data X_test with IA_test

        Parameters
        ----------
        X_test : test data [N,d]
        IA_test : training incidence angle [N,1] or [N,]
    
        Returns
        -------
        y_pred : predicted class label [N,]
        p : probabilities [N,n_class]
        """

        assert len(X_test.shape) == 2, 'Test data must be of shape (N,d)'

        assert X_test.shape[0] == IA_test.shape[0], 'X_test and IA_test must have same number of samples'

        N_test, d_test = X_test.shape
        self.logger.debug(f'Number of test points: {N_test}')
        self.logger.debug(f'Number of dimensions: {d_test}')

        print(self.n_feat)
        assert d_test == self.n_feat, f'Classifier is trained with {self.n_feat} features but X_test has {d_test} features'

        p      = np.full([N_test, self.n_class], np.nan)
        y_pred = np.full([N_test], np.nan)

        for cl in (self.trained_classes):
            self.logger.debug(f'Working on class {cl}')
            self.logger.debug('Projecting data according to current class slopes.')

            X_test_projected = np.zeros(X_test.shape)

            # correct X according to class-dependent slope
            for feat in range(self.n_feat):
                self.logger.debug(f'Projecting current class along feature dimension {feat}')
                X_test_projected[:,feat] = X_test[:,feat] - self.b[cl-1,feat] * (IA_test-self.IA_0)

            # estimate p from multivariate_normal on projected data
            self.logger.debug(f'Calculating p for class {cl}')
           

            p[:,cl-1] = self.class_mvn[str(cl)].pdf(X_test_projected)

     
        y_pred  = np.nanargmax(p,1) + 1

        return y_pred, p