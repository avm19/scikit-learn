import re

import numpy as np
import scipy.sparse
import pytest
from itertools import chain
import warnings

from sklearn.datasets import load_digits, load_iris

from sklearn.model_selection import train_test_split
from sklearn.model_selection import cross_val_score

from sklearn.utils._testing import assert_almost_equal
from sklearn.utils._testing import assert_array_equal
from sklearn.utils._testing import assert_array_almost_equal

from sklearn.naive_bayes import GaussianNB, BernoulliNB
from sklearn.naive_bayes import MultinomialNB, ComplementNB
from sklearn.naive_bayes import CategoricalNB

from sklearn.base import BaseEstimator
from sklearn.base import clone
from sklearn.compose import make_column_selector
from sklearn.exceptions import DataConversionWarning
from sklearn.naive_bayes import ColumnwiseNB

DISCRETE_NAIVE_BAYES_CLASSES = [BernoulliNB, CategoricalNB, ComplementNB, MultinomialNB]
ALL_NAIVE_BAYES_CLASSES = DISCRETE_NAIVE_BAYES_CLASSES + [GaussianNB]


# Data is just 6 separable points in the plane
X = np.array([[-2, -1], [-1, -1], [-1, -2], [1, 1], [1, 2], [2, 1]])
y = np.array([1, 1, 1, 2, 2, 2])

# A bit more random tests
rng = np.random.RandomState(0)
X1 = rng.normal(size=(10, 3))
y1 = (rng.normal(size=(10)) > 0).astype(int)

# Data is 6 random integer points in a 100 dimensional space classified to
# three classes.
X2 = rng.randint(5, size=(6, 100))
y2 = np.array([1, 1, 2, 2, 3, 3])


def test_gnb():
    # Gaussian Naive Bayes classification.
    # This checks that GaussianNB implements fit and predict and returns
    # correct values for a simple toy dataset.

    clf = GaussianNB()
    y_pred = clf.fit(X, y).predict(X)
    assert_array_equal(y_pred, y)

    y_pred_proba = clf.predict_proba(X)
    y_pred_log_proba = clf.predict_log_proba(X)
    assert_array_almost_equal(np.log(y_pred_proba), y_pred_log_proba, 8)

    # Test whether label mismatch between target y and classes raises
    # an Error
    # FIXME Remove this test once the more general partial_fit tests are merged
    with pytest.raises(
        ValueError, match="The target label.* in y do not exist in the initial classes"
    ):
        GaussianNB().partial_fit(X, y, classes=[0, 1])


# TODO remove in 1.2 once sigma_ attribute is removed (GH #18842)
def test_gnb_var():
    clf = GaussianNB()
    clf.fit(X, y)

    with pytest.warns(FutureWarning, match="Attribute `sigma_` was deprecated"):
        assert_array_equal(clf.sigma_, clf.var_)


def test_gnb_prior():
    # Test whether class priors are properly set.
    clf = GaussianNB().fit(X, y)
    assert_array_almost_equal(np.array([3, 3]) / 6.0, clf.class_prior_, 8)
    clf = GaussianNB().fit(X1, y1)
    # Check that the class priors sum to 1
    assert_array_almost_equal(clf.class_prior_.sum(), 1)


def test_gnb_sample_weight():
    """Test whether sample weights are properly used in GNB."""
    # Sample weights all being 1 should not change results
    sw = np.ones(6)
    clf = GaussianNB().fit(X, y)
    clf_sw = GaussianNB().fit(X, y, sw)

    assert_array_almost_equal(clf.theta_, clf_sw.theta_)
    assert_array_almost_equal(clf.var_, clf_sw.var_)

    # Fitting twice with half sample-weights should result
    # in same result as fitting once with full weights
    sw = rng.rand(y.shape[0])
    clf1 = GaussianNB().fit(X, y, sample_weight=sw)
    clf2 = GaussianNB().partial_fit(X, y, classes=[1, 2], sample_weight=sw / 2)
    clf2.partial_fit(X, y, sample_weight=sw / 2)

    assert_array_almost_equal(clf1.theta_, clf2.theta_)
    assert_array_almost_equal(clf1.var_, clf2.var_)

    # Check that duplicate entries and correspondingly increased sample
    # weights yield the same result
    ind = rng.randint(0, X.shape[0], 20)
    sample_weight = np.bincount(ind, minlength=X.shape[0])

    clf_dupl = GaussianNB().fit(X[ind], y[ind])
    clf_sw = GaussianNB().fit(X, y, sample_weight)

    assert_array_almost_equal(clf_dupl.theta_, clf_sw.theta_)
    assert_array_almost_equal(clf_dupl.var_, clf_sw.var_)


def test_gnb_neg_priors():
    """Test whether an error is raised in case of negative priors"""
    clf = GaussianNB(priors=np.array([-1.0, 2.0]))

    msg = "Priors must be non-negative"
    with pytest.raises(ValueError, match=msg):
        clf.fit(X, y)


def test_gnb_priors():
    """Test whether the class prior override is properly used"""
    clf = GaussianNB(priors=np.array([0.3, 0.7])).fit(X, y)
    assert_array_almost_equal(
        clf.predict_proba([[-0.1, -0.1]]),
        np.array([[0.825303662161683, 0.174696337838317]]),
        8,
    )
    assert_array_almost_equal(clf.class_prior_, np.array([0.3, 0.7]))


def test_gnb_priors_sum_isclose():
    # test whether the class prior sum is properly tested"""
    X = np.array(
        [
            [-1, -1],
            [-2, -1],
            [-3, -2],
            [-4, -5],
            [-5, -4],
            [1, 1],
            [2, 1],
            [3, 2],
            [4, 4],
            [5, 5],
        ]
    )
    priors = np.array([0.08, 0.14, 0.03, 0.16, 0.11, 0.16, 0.07, 0.14, 0.11, 0.0])
    Y = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    clf = GaussianNB(priors=priors)
    # smoke test for issue #9633
    clf.fit(X, Y)


def test_gnb_wrong_nb_priors():
    """Test whether an error is raised if the number of prior is different
    from the number of class"""
    clf = GaussianNB(priors=np.array([0.25, 0.25, 0.25, 0.25]))

    msg = "Number of priors must match number of classes"
    with pytest.raises(ValueError, match=msg):
        clf.fit(X, y)


def test_gnb_prior_greater_one():
    """Test if an error is raised if the sum of prior greater than one"""
    clf = GaussianNB(priors=np.array([2.0, 1.0]))

    msg = "The sum of the priors should be 1"
    with pytest.raises(ValueError, match=msg):
        clf.fit(X, y)


def test_gnb_prior_large_bias():
    """Test if good prediction when class prior favor largely one class"""
    clf = GaussianNB(priors=np.array([0.01, 0.99]))
    clf.fit(X, y)
    assert clf.predict([[-0.1, -0.1]]) == np.array([2])


def test_gnb_check_update_with_no_data():
    """Test when the partial fit is called without any data"""
    # Create an empty array
    prev_points = 100
    mean = 0.0
    var = 1.0
    x_empty = np.empty((0, X.shape[1]))
    tmean, tvar = GaussianNB._update_mean_variance(prev_points, mean, var, x_empty)
    assert tmean == mean
    assert tvar == var


def test_gnb_partial_fit():
    clf = GaussianNB().fit(X, y)
    clf_pf = GaussianNB().partial_fit(X, y, np.unique(y))
    assert_array_almost_equal(clf.theta_, clf_pf.theta_)
    assert_array_almost_equal(clf.var_, clf_pf.var_)
    assert_array_almost_equal(clf.class_prior_, clf_pf.class_prior_)

    clf_pf2 = GaussianNB().partial_fit(X[0::2, :], y[0::2], np.unique(y))
    clf_pf2.partial_fit(X[1::2], y[1::2])
    assert_array_almost_equal(clf.theta_, clf_pf2.theta_)
    assert_array_almost_equal(clf.var_, clf_pf2.var_)
    assert_array_almost_equal(clf.class_prior_, clf_pf2.class_prior_)


def test_gnb_naive_bayes_scale_invariance():
    # Scaling the data should not change the prediction results
    iris = load_iris()
    X, y = iris.data, iris.target
    labels = [GaussianNB().fit(f * X, y).predict(f * X) for f in [1e-10, 1, 1e10]]
    assert_array_equal(labels[0], labels[1])
    assert_array_equal(labels[1], labels[2])


@pytest.mark.parametrize("DiscreteNaiveBayes", DISCRETE_NAIVE_BAYES_CLASSES)
def test_discretenb_prior(DiscreteNaiveBayes):
    # Test whether class priors are properly set.
    clf = DiscreteNaiveBayes().fit(X2, y2)
    assert_array_almost_equal(
        np.log(np.array([2, 2, 2]) / 6.0), clf.class_log_prior_, 8
    )


@pytest.mark.parametrize("DiscreteNaiveBayes", DISCRETE_NAIVE_BAYES_CLASSES)
def test_discretenb_partial_fit(DiscreteNaiveBayes):
    clf1 = DiscreteNaiveBayes()
    clf1.fit([[0, 1], [1, 0], [1, 1]], [0, 1, 1])

    clf2 = DiscreteNaiveBayes()
    clf2.partial_fit([[0, 1], [1, 0], [1, 1]], [0, 1, 1], classes=[0, 1])
    assert_array_equal(clf1.class_count_, clf2.class_count_)
    if DiscreteNaiveBayes is CategoricalNB:
        for i in range(len(clf1.category_count_)):
            assert_array_equal(clf1.category_count_[i], clf2.category_count_[i])
    else:
        assert_array_equal(clf1.feature_count_, clf2.feature_count_)

    clf3 = DiscreteNaiveBayes()
    # all categories have to appear in the first partial fit
    clf3.partial_fit([[0, 1]], [0], classes=[0, 1])
    clf3.partial_fit([[1, 0]], [1])
    clf3.partial_fit([[1, 1]], [1])
    assert_array_equal(clf1.class_count_, clf3.class_count_)
    if DiscreteNaiveBayes is CategoricalNB:
        # the categories for each feature of CategoricalNB are mapped to an
        # index chronologically with each call of partial fit and therefore
        # the category_count matrices cannot be compared for equality
        for i in range(len(clf1.category_count_)):
            assert_array_equal(
                clf1.category_count_[i].shape, clf3.category_count_[i].shape
            )
            assert_array_equal(
                np.sum(clf1.category_count_[i], axis=1),
                np.sum(clf3.category_count_[i], axis=1),
            )

        # assert category 0 occurs 1x in the first class and 0x in the 2nd
        # class
        assert_array_equal(clf1.category_count_[0][0], np.array([1, 0]))
        # assert category 1 occurs 0x in the first class and 2x in the 2nd
        # class
        assert_array_equal(clf1.category_count_[0][1], np.array([0, 2]))

        # assert category 0 occurs 0x in the first class and 1x in the 2nd
        # class
        assert_array_equal(clf1.category_count_[1][0], np.array([0, 1]))
        # assert category 1 occurs 1x in the first class and 1x in the 2nd
        # class
        assert_array_equal(clf1.category_count_[1][1], np.array([1, 1]))
    else:
        assert_array_equal(clf1.feature_count_, clf3.feature_count_)


@pytest.mark.parametrize("NaiveBayes", ALL_NAIVE_BAYES_CLASSES)
def test_NB_partial_fit_no_first_classes(NaiveBayes):
    # classes is required for first call to partial fit
    with pytest.raises(
        ValueError, match="classes must be passed on the first call to partial_fit."
    ):
        NaiveBayes().partial_fit(X2, y2)

    # check consistency of consecutive classes values
    clf = NaiveBayes()
    clf.partial_fit(X2, y2, classes=np.unique(y2))
    with pytest.raises(
        ValueError, match="is not the same as on last call to partial_fit"
    ):
        clf.partial_fit(X2, y2, classes=np.arange(42))


def test_discretenb_predict_proba():
    # Test discrete NB classes' probability scores

    # The 100s below distinguish Bernoulli from multinomial.
    # FIXME: write a test to show this.
    X_bernoulli = [[1, 100, 0], [0, 1, 0], [0, 100, 1]]
    X_multinomial = [[0, 1], [1, 3], [4, 0]]

    # test binary case (1-d output)
    y = [0, 0, 2]  # 2 is regression test for binary case, 02e673
    for DiscreteNaiveBayes, X in zip(
        [BernoulliNB, MultinomialNB], [X_bernoulli, X_multinomial]
    ):
        clf = DiscreteNaiveBayes().fit(X, y)
        assert clf.predict(X[-1:]) == 2
        assert clf.predict_proba([X[0]]).shape == (1, 2)
        assert_array_almost_equal(
            clf.predict_proba(X[:2]).sum(axis=1), np.array([1.0, 1.0]), 6
        )

    # test multiclass case (2-d output, must sum to one)
    y = [0, 1, 2]
    for DiscreteNaiveBayes, X in zip(
        [BernoulliNB, MultinomialNB], [X_bernoulli, X_multinomial]
    ):
        clf = DiscreteNaiveBayes().fit(X, y)
        assert clf.predict_proba(X[0:1]).shape == (1, 3)
        assert clf.predict_proba(X[:2]).shape == (2, 3)
        assert_almost_equal(np.sum(clf.predict_proba([X[1]])), 1)
        assert_almost_equal(np.sum(clf.predict_proba([X[-1]])), 1)
        assert_almost_equal(np.sum(np.exp(clf.class_log_prior_)), 1)


@pytest.mark.parametrize("DiscreteNaiveBayes", DISCRETE_NAIVE_BAYES_CLASSES)
def test_discretenb_uniform_prior(DiscreteNaiveBayes):
    # Test whether discrete NB classes fit a uniform prior
    # when fit_prior=False and class_prior=None

    clf = DiscreteNaiveBayes()
    clf.set_params(fit_prior=False)
    clf.fit([[0], [0], [1]], [0, 0, 1])
    prior = np.exp(clf.class_log_prior_)
    assert_array_almost_equal(prior, np.array([0.5, 0.5]))


@pytest.mark.parametrize("DiscreteNaiveBayes", DISCRETE_NAIVE_BAYES_CLASSES)
def test_discretenb_provide_prior(DiscreteNaiveBayes):
    # Test whether discrete NB classes use provided prior

    clf = DiscreteNaiveBayes(class_prior=[0.5, 0.5])
    clf.fit([[0], [0], [1]], [0, 0, 1])
    prior = np.exp(clf.class_log_prior_)
    assert_array_almost_equal(prior, np.array([0.5, 0.5]))

    # Inconsistent number of classes with prior
    msg = "Number of priors must match number of classes"
    with pytest.raises(ValueError, match=msg):
        clf.fit([[0], [1], [2]], [0, 1, 2])

    msg = "is not the same as on last call to partial_fit"
    with pytest.raises(ValueError, match=msg):
        clf.partial_fit([[0], [1]], [0, 1], classes=[0, 1, 1])


@pytest.mark.parametrize("DiscreteNaiveBayes", DISCRETE_NAIVE_BAYES_CLASSES)
def test_discretenb_provide_prior_with_partial_fit(DiscreteNaiveBayes):
    # Test whether discrete NB classes use provided prior
    # when using partial_fit

    iris = load_iris()
    iris_data1, iris_data2, iris_target1, iris_target2 = train_test_split(
        iris.data, iris.target, test_size=0.4, random_state=415
    )

    for prior in [None, [0.3, 0.3, 0.4]]:
        clf_full = DiscreteNaiveBayes(class_prior=prior)
        clf_full.fit(iris.data, iris.target)
        clf_partial = DiscreteNaiveBayes(class_prior=prior)
        clf_partial.partial_fit(iris_data1, iris_target1, classes=[0, 1, 2])
        clf_partial.partial_fit(iris_data2, iris_target2)
        assert_array_almost_equal(
            clf_full.class_log_prior_, clf_partial.class_log_prior_
        )


@pytest.mark.parametrize("DiscreteNaiveBayes", DISCRETE_NAIVE_BAYES_CLASSES)
def test_discretenb_sample_weight_multiclass(DiscreteNaiveBayes):
    # check shape consistency for number of samples at fit time
    X = [
        [0, 0, 1],
        [0, 1, 1],
        [0, 1, 1],
        [1, 0, 0],
    ]
    y = [0, 0, 1, 2]
    sample_weight = np.array([1, 1, 2, 2], dtype=np.float64)
    sample_weight /= sample_weight.sum()
    clf = DiscreteNaiveBayes().fit(X, y, sample_weight=sample_weight)
    assert_array_equal(clf.predict(X), [0, 1, 1, 2])

    # Check sample weight using the partial_fit method
    clf = DiscreteNaiveBayes()
    clf.partial_fit(X[:2], y[:2], classes=[0, 1, 2], sample_weight=sample_weight[:2])
    clf.partial_fit(X[2:3], y[2:3], sample_weight=sample_weight[2:3])
    clf.partial_fit(X[3:], y[3:], sample_weight=sample_weight[3:])
    assert_array_equal(clf.predict(X), [0, 1, 1, 2])


@pytest.mark.parametrize("DiscreteNaiveBayes", DISCRETE_NAIVE_BAYES_CLASSES)
@pytest.mark.parametrize("use_partial_fit", [False, True])
@pytest.mark.parametrize("train_on_single_class_y", [False, True])
def test_discretenb_degenerate_one_class_case(
    DiscreteNaiveBayes,
    use_partial_fit,
    train_on_single_class_y,
):
    # Most array attributes of a discrete naive Bayes classifier should have a
    # first-axis length equal to the number of classes. Exceptions include:
    # ComplementNB.feature_all_, CategoricalNB.n_categories_.
    # Confirm that this is the case for binary problems and the degenerate
    # case of a single class in the training set, when fitting with `fit` or
    # `partial_fit`.
    # Non-regression test for handling degenerate one-class case:
    # https://github.com/scikit-learn/scikit-learn/issues/18974

    X = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    y = [1, 1, 2]
    if train_on_single_class_y:
        X = X[:-1]
        y = y[:-1]
    classes = sorted(list(set(y)))
    num_classes = len(classes)

    clf = DiscreteNaiveBayes()
    if use_partial_fit:
        clf.partial_fit(X, y, classes=classes)
    else:
        clf.fit(X, y)
    assert clf.predict(X[:1]) == y[0]

    # Check that attributes have expected first-axis lengths
    attribute_names = [
        "classes_",
        "class_count_",
        "class_log_prior_",
        "feature_count_",
        "feature_log_prob_",
    ]
    for attribute_name in attribute_names:
        attribute = getattr(clf, attribute_name, None)
        if attribute is None:
            # CategoricalNB has no feature_count_ attribute
            continue
        if isinstance(attribute, np.ndarray):
            assert attribute.shape[0] == num_classes
        else:
            # CategoricalNB.feature_log_prob_ is a list of arrays
            for element in attribute:
                assert element.shape[0] == num_classes


@pytest.mark.parametrize("kind", ("dense", "sparse"))
def test_mnnb(kind):
    # Test Multinomial Naive Bayes classification.
    # This checks that MultinomialNB implements fit and predict and returns
    # correct values for a simple toy dataset.

    if kind == "dense":
        X = X2
    elif kind == "sparse":
        X = scipy.sparse.csr_matrix(X2)

    # Check the ability to predict the learning set.
    clf = MultinomialNB()

    msg = "Negative values in data passed to"
    with pytest.raises(ValueError, match=msg):
        clf.fit(-X, y2)
    y_pred = clf.fit(X, y2).predict(X)

    assert_array_equal(y_pred, y2)

    # Verify that np.log(clf.predict_proba(X)) gives the same results as
    # clf.predict_log_proba(X)
    y_pred_proba = clf.predict_proba(X)
    y_pred_log_proba = clf.predict_log_proba(X)
    assert_array_almost_equal(np.log(y_pred_proba), y_pred_log_proba, 8)

    # Check that incremental fitting yields the same results
    clf2 = MultinomialNB()
    clf2.partial_fit(X[:2], y2[:2], classes=np.unique(y2))
    clf2.partial_fit(X[2:5], y2[2:5])
    clf2.partial_fit(X[5:], y2[5:])

    y_pred2 = clf2.predict(X)
    assert_array_equal(y_pred2, y2)

    y_pred_proba2 = clf2.predict_proba(X)
    y_pred_log_proba2 = clf2.predict_log_proba(X)
    assert_array_almost_equal(np.log(y_pred_proba2), y_pred_log_proba2, 8)
    assert_array_almost_equal(y_pred_proba2, y_pred_proba)
    assert_array_almost_equal(y_pred_log_proba2, y_pred_log_proba)

    # Partial fit on the whole data at once should be the same as fit too
    clf3 = MultinomialNB()
    clf3.partial_fit(X, y2, classes=np.unique(y2))

    y_pred3 = clf3.predict(X)
    assert_array_equal(y_pred3, y2)
    y_pred_proba3 = clf3.predict_proba(X)
    y_pred_log_proba3 = clf3.predict_log_proba(X)
    assert_array_almost_equal(np.log(y_pred_proba3), y_pred_log_proba3, 8)
    assert_array_almost_equal(y_pred_proba3, y_pred_proba)
    assert_array_almost_equal(y_pred_log_proba3, y_pred_log_proba)


def test_mnb_prior_unobserved_targets():
    # test smoothing of prior for yet unobserved targets

    # Create toy training data
    X = np.array([[0, 1], [1, 0]])
    y = np.array([0, 1])

    clf = MultinomialNB()

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)

        clf.partial_fit(X, y, classes=[0, 1, 2])

    assert clf.predict([[0, 1]]) == 0
    assert clf.predict([[1, 0]]) == 1
    assert clf.predict([[1, 1]]) == 0

    # add a training example with previously unobserved class
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)

        clf.partial_fit([[1, 1]], [2])

    assert clf.predict([[0, 1]]) == 0
    assert clf.predict([[1, 0]]) == 1
    assert clf.predict([[1, 1]]) == 2


def test_bnb():
    # Tests that BernoulliNB when alpha=1.0 gives the same values as
    # those given for the toy example in Manning, Raghavan, and
    # Schuetze's "Introduction to Information Retrieval" book:
    # https://nlp.stanford.edu/IR-book/html/htmledition/the-bernoulli-model-1.html

    # Training data points are:
    # Chinese Beijing Chinese (class: China)
    # Chinese Chinese Shanghai (class: China)
    # Chinese Macao (class: China)
    # Tokyo Japan Chinese (class: Japan)

    # Features are Beijing, Chinese, Japan, Macao, Shanghai, and Tokyo
    X = np.array(
        [[1, 1, 0, 0, 0, 0], [0, 1, 0, 0, 1, 0], [0, 1, 0, 1, 0, 0], [0, 1, 1, 0, 0, 1]]
    )

    # Classes are China (0), Japan (1)
    Y = np.array([0, 0, 0, 1])

    # Fit BernoulliBN w/ alpha = 1.0
    clf = BernoulliNB(alpha=1.0)
    clf.fit(X, Y)

    # Check the class prior is correct
    class_prior = np.array([0.75, 0.25])
    assert_array_almost_equal(np.exp(clf.class_log_prior_), class_prior)

    # Check the feature probabilities are correct
    feature_prob = np.array(
        [
            [0.4, 0.8, 0.2, 0.4, 0.4, 0.2],
            [1 / 3.0, 2 / 3.0, 2 / 3.0, 1 / 3.0, 1 / 3.0, 2 / 3.0],
        ]
    )
    assert_array_almost_equal(np.exp(clf.feature_log_prob_), feature_prob)

    # Testing data point is:
    # Chinese Chinese Chinese Tokyo Japan
    X_test = np.array([[0, 1, 1, 0, 0, 1]])

    # Check the predictive probabilities are correct
    unnorm_predict_proba = np.array([[0.005183999999999999, 0.02194787379972565]])
    predict_proba = unnorm_predict_proba / np.sum(unnorm_predict_proba)
    assert_array_almost_equal(clf.predict_proba(X_test), predict_proba)


def test_bnb_feature_log_prob():
    # Test for issue #4268.
    # Tests that the feature log prob value computed by BernoulliNB when
    # alpha=1.0 is equal to the expression given in Manning, Raghavan,
    # and Schuetze's "Introduction to Information Retrieval" book:
    # http://nlp.stanford.edu/IR-book/html/htmledition/the-bernoulli-model-1.html

    X = np.array([[0, 0, 0], [1, 1, 0], [0, 1, 0], [1, 0, 1], [0, 1, 0]])
    Y = np.array([0, 0, 1, 2, 2])

    # Fit Bernoulli NB w/ alpha = 1.0
    clf = BernoulliNB(alpha=1.0)
    clf.fit(X, Y)

    # Manually form the (log) numerator and denominator that
    # constitute P(feature presence | class)
    num = np.log(clf.feature_count_ + 1.0)
    denom = np.tile(np.log(clf.class_count_ + 2.0), (X.shape[1], 1)).T

    # Check manual estimate matches
    assert_array_almost_equal(clf.feature_log_prob_, (num - denom))


def test_cnb():
    # Tests ComplementNB when alpha=1.0 for the toy example in Manning,
    # Raghavan, and Schuetze's "Introduction to Information Retrieval" book:
    # https://nlp.stanford.edu/IR-book/html/htmledition/the-bernoulli-model-1.html

    # Training data points are:
    # Chinese Beijing Chinese (class: China)
    # Chinese Chinese Shanghai (class: China)
    # Chinese Macao (class: China)
    # Tokyo Japan Chinese (class: Japan)

    # Features are Beijing, Chinese, Japan, Macao, Shanghai, and Tokyo.
    X = np.array(
        [[1, 1, 0, 0, 0, 0], [0, 1, 0, 0, 1, 0], [0, 1, 0, 1, 0, 0], [0, 1, 1, 0, 0, 1]]
    )

    # Classes are China (0), Japan (1).
    Y = np.array([0, 0, 0, 1])

    # Check that weights are correct. See steps 4-6 in Table 4 of
    # Rennie et al. (2003).
    theta = np.array(
        [
            [
                (0 + 1) / (3 + 6),
                (1 + 1) / (3 + 6),
                (1 + 1) / (3 + 6),
                (0 + 1) / (3 + 6),
                (0 + 1) / (3 + 6),
                (1 + 1) / (3 + 6),
            ],
            [
                (1 + 1) / (6 + 6),
                (3 + 1) / (6 + 6),
                (0 + 1) / (6 + 6),
                (1 + 1) / (6 + 6),
                (1 + 1) / (6 + 6),
                (0 + 1) / (6 + 6),
            ],
        ]
    )

    weights = np.zeros(theta.shape)
    normed_weights = np.zeros(theta.shape)
    for i in range(2):
        weights[i] = -np.log(theta[i])
        normed_weights[i] = weights[i] / weights[i].sum()

    # Verify inputs are nonnegative.
    clf = ComplementNB(alpha=1.0)

    msg = re.escape("Negative values in data passed to ComplementNB (input X)")
    with pytest.raises(ValueError, match=msg):
        clf.fit(-X, Y)

    clf.fit(X, Y)

    # Check that counts/weights are correct.
    feature_count = np.array([[1, 3, 0, 1, 1, 0], [0, 1, 1, 0, 0, 1]])
    assert_array_equal(clf.feature_count_, feature_count)
    class_count = np.array([3, 1])
    assert_array_equal(clf.class_count_, class_count)
    feature_all = np.array([1, 4, 1, 1, 1, 1])
    assert_array_equal(clf.feature_all_, feature_all)
    assert_array_almost_equal(clf.feature_log_prob_, weights)

    clf = ComplementNB(alpha=1.0, norm=True)
    clf.fit(X, Y)
    assert_array_almost_equal(clf.feature_log_prob_, normed_weights)


def test_categoricalnb():
    # Check the ability to predict the training set.
    clf = CategoricalNB()
    y_pred = clf.fit(X2, y2).predict(X2)
    assert_array_equal(y_pred, y2)

    X3 = np.array([[1, 4], [2, 5]])
    y3 = np.array([1, 2])
    clf = CategoricalNB(alpha=1, fit_prior=False)

    clf.fit(X3, y3)
    assert_array_equal(clf.n_categories_, np.array([3, 6]))

    # Check error is raised for X with negative entries
    X = np.array([[0, -1]])
    y = np.array([1])
    error_msg = re.escape("Negative values in data passed to CategoricalNB (input X)")
    with pytest.raises(ValueError, match=error_msg):
        clf.predict(X)
    with pytest.raises(ValueError, match=error_msg):
        clf.fit(X, y)

    # Test alpha
    X3_test = np.array([[2, 5]])
    # alpha=1 increases the count of all categories by one so the final
    # probability for each category is not 50/50 but 1/3 to 2/3
    bayes_numerator = np.array([[1 / 3 * 1 / 3, 2 / 3 * 2 / 3]])
    bayes_denominator = bayes_numerator.sum()
    assert_array_almost_equal(
        clf.predict_proba(X3_test), bayes_numerator / bayes_denominator
    )

    # Assert category_count has counted all features
    assert len(clf.category_count_) == X3.shape[1]

    # Check sample_weight
    X = np.array([[0, 0], [0, 1], [0, 0], [1, 1]])
    y = np.array([1, 1, 2, 2])
    clf = CategoricalNB(alpha=1, fit_prior=False)
    clf.fit(X, y)
    assert_array_equal(clf.predict(np.array([[0, 0]])), np.array([1]))
    assert_array_equal(clf.n_categories_, np.array([2, 2]))

    for factor in [1.0, 0.3, 5, 0.0001]:
        X = np.array([[0, 0], [0, 1], [0, 0], [1, 1]])
        y = np.array([1, 1, 2, 2])
        sample_weight = np.array([1, 1, 10, 0.1]) * factor
        clf = CategoricalNB(alpha=1, fit_prior=False)
        clf.fit(X, y, sample_weight=sample_weight)
        assert_array_equal(clf.predict(np.array([[0, 0]])), np.array([2]))
        assert_array_equal(clf.n_categories_, np.array([2, 2]))


@pytest.mark.parametrize(
    "min_categories, exp_X1_count, exp_X2_count, new_X, exp_n_categories_",
    [
        # check min_categories with int > observed categories
        (
            3,
            np.array([[2, 0, 0], [1, 1, 0]]),
            np.array([[1, 1, 0], [1, 1, 0]]),
            np.array([[0, 2]]),
            np.array([3, 3]),
        ),
        # check with list input
        (
            [3, 4],
            np.array([[2, 0, 0], [1, 1, 0]]),
            np.array([[1, 1, 0, 0], [1, 1, 0, 0]]),
            np.array([[0, 3]]),
            np.array([3, 4]),
        ),
        # check min_categories with min less than actual
        (
            [
                1,
                np.array([[2, 0], [1, 1]]),
                np.array([[1, 1], [1, 1]]),
                np.array([[0, 1]]),
                np.array([2, 2]),
            ]
        ),
    ],
)
def test_categoricalnb_with_min_categories(
    min_categories, exp_X1_count, exp_X2_count, new_X, exp_n_categories_
):
    X_n_categories = np.array([[0, 0], [0, 1], [0, 0], [1, 1]])
    y_n_categories = np.array([1, 1, 2, 2])
    expected_prediction = np.array([1])

    clf = CategoricalNB(alpha=1, fit_prior=False, min_categories=min_categories)
    clf.fit(X_n_categories, y_n_categories)
    X1_count, X2_count = clf.category_count_
    assert_array_equal(X1_count, exp_X1_count)
    assert_array_equal(X2_count, exp_X2_count)
    predictions = clf.predict(new_X)
    assert_array_equal(predictions, expected_prediction)
    assert_array_equal(clf.n_categories_, exp_n_categories_)


@pytest.mark.parametrize(
    "min_categories, error_msg",
    [
        ("bad_arg", "'min_categories' should have integral"),
        ([[3, 2], [2, 4]], "'min_categories' should have shape"),
        (1.0, "'min_categories' should have integral"),
    ],
)
def test_categoricalnb_min_categories_errors(min_categories, error_msg):

    X = np.array([[0, 0], [0, 1], [0, 0], [1, 1]])
    y = np.array([1, 1, 2, 2])

    clf = CategoricalNB(alpha=1, fit_prior=False, min_categories=min_categories)
    with pytest.raises(ValueError, match=error_msg):
        clf.fit(X, y)


def test_alpha():
    # Setting alpha=0 should not output nan results when p(x_i|y_j)=0 is a case
    X = np.array([[1, 0], [1, 1]])
    y = np.array([0, 1])
    nb = BernoulliNB(alpha=0.0)
    msg = "alpha too small will result in numeric errors, setting alpha = 1.0e-10"
    with pytest.warns(UserWarning, match=msg):
        nb.partial_fit(X, y, classes=[0, 1])
    with pytest.warns(UserWarning, match=msg):
        nb.fit(X, y)
    prob = np.array([[1, 0], [0, 1]])
    assert_array_almost_equal(nb.predict_proba(X), prob)

    nb = MultinomialNB(alpha=0.0)
    with pytest.warns(UserWarning, match=msg):
        nb.partial_fit(X, y, classes=[0, 1])
    with pytest.warns(UserWarning, match=msg):
        nb.fit(X, y)
    prob = np.array([[2.0 / 3, 1.0 / 3], [0, 1]])
    assert_array_almost_equal(nb.predict_proba(X), prob)

    nb = CategoricalNB(alpha=0.0)
    with pytest.warns(UserWarning, match=msg):
        nb.fit(X, y)
    prob = np.array([[1.0, 0.0], [0.0, 1.0]])
    assert_array_almost_equal(nb.predict_proba(X), prob)

    # Test sparse X
    X = scipy.sparse.csr_matrix(X)
    nb = BernoulliNB(alpha=0.0)
    with pytest.warns(UserWarning, match=msg):
        nb.fit(X, y)
    prob = np.array([[1, 0], [0, 1]])
    assert_array_almost_equal(nb.predict_proba(X), prob)

    nb = MultinomialNB(alpha=0.0)
    with pytest.warns(UserWarning, match=msg):
        nb.fit(X, y)
    prob = np.array([[2.0 / 3, 1.0 / 3], [0, 1]])
    assert_array_almost_equal(nb.predict_proba(X), prob)

    # Test for alpha < 0
    X = np.array([[1, 0], [1, 1]])
    y = np.array([0, 1])
    expected_msg = re.escape(
        "Smoothing parameter alpha = -1.0e-01. alpha should be > 0."
    )
    b_nb = BernoulliNB(alpha=-0.1)
    m_nb = MultinomialNB(alpha=-0.1)
    c_nb = CategoricalNB(alpha=-0.1)
    with pytest.raises(ValueError, match=expected_msg):
        b_nb.fit(X, y)
    with pytest.raises(ValueError, match=expected_msg):
        m_nb.fit(X, y)
    with pytest.raises(ValueError, match=expected_msg):
        c_nb.fit(X, y)

    b_nb = BernoulliNB(alpha=-0.1)
    m_nb = MultinomialNB(alpha=-0.1)
    with pytest.raises(ValueError, match=expected_msg):
        b_nb.partial_fit(X, y, classes=[0, 1])
    with pytest.raises(ValueError, match=expected_msg):
        m_nb.partial_fit(X, y, classes=[0, 1])


def test_alpha_vector():
    X = np.array([[1, 0], [1, 1]])
    y = np.array([0, 1])

    # Setting alpha=np.array with same length
    # as number of features should be fine
    alpha = np.array([1, 2])
    nb = MultinomialNB(alpha=alpha)
    nb.partial_fit(X, y, classes=[0, 1])

    # Test feature probabilities uses pseudo-counts (alpha)
    feature_prob = np.array([[1 / 2, 1 / 2], [2 / 5, 3 / 5]])
    assert_array_almost_equal(nb.feature_log_prob_, np.log(feature_prob))

    # Test predictions
    prob = np.array([[5 / 9, 4 / 9], [25 / 49, 24 / 49]])
    assert_array_almost_equal(nb.predict_proba(X), prob)

    # Test alpha non-negative
    alpha = np.array([1.0, -0.1])
    m_nb = MultinomialNB(alpha=alpha)
    expected_msg = "Smoothing parameter alpha = -1.0e-01. alpha should be > 0."
    with pytest.raises(ValueError, match=expected_msg):
        m_nb.fit(X, y)

    # Test that too small pseudo-counts are replaced
    ALPHA_MIN = 1e-10
    alpha = np.array([ALPHA_MIN / 2, 0.5])
    m_nb = MultinomialNB(alpha=alpha)
    m_nb.partial_fit(X, y, classes=[0, 1])
    assert_array_almost_equal(m_nb._check_alpha(), [ALPHA_MIN, 0.5], decimal=12)

    # Test correct dimensions
    alpha = np.array([1.0, 2.0, 3.0])
    m_nb = MultinomialNB(alpha=alpha)
    expected_msg = re.escape(
        "alpha should be a scalar or a numpy array with shape [n_features]"
    )
    with pytest.raises(ValueError, match=expected_msg):
        m_nb.fit(X, y)


def test_check_accuracy_on_digits():
    # Non regression test to make sure that any further refactoring / optim
    # of the NB models do not harm the performance on a slightly non-linearly
    # separable dataset
    X, y = load_digits(return_X_y=True)
    binary_3v8 = np.logical_or(y == 3, y == 8)
    X_3v8, y_3v8 = X[binary_3v8], y[binary_3v8]

    # Multinomial NB
    scores = cross_val_score(MultinomialNB(alpha=10), X, y, cv=10)
    assert scores.mean() > 0.86

    scores = cross_val_score(MultinomialNB(alpha=10), X_3v8, y_3v8, cv=10)
    assert scores.mean() > 0.94

    # Bernoulli NB
    scores = cross_val_score(BernoulliNB(alpha=10), X > 4, y, cv=10)
    assert scores.mean() > 0.83

    scores = cross_val_score(BernoulliNB(alpha=10), X_3v8 > 4, y_3v8, cv=10)
    assert scores.mean() > 0.92

    # Gaussian NB
    scores = cross_val_score(GaussianNB(), X, y, cv=10)
    assert scores.mean() > 0.77

    scores = cross_val_score(GaussianNB(var_smoothing=0.1), X, y, cv=10)
    assert scores.mean() > 0.89

    scores = cross_val_score(GaussianNB(), X_3v8, y_3v8, cv=10)
    assert scores.mean() > 0.86


# FIXME: remove in 1.2
@pytest.mark.parametrize("Estimator", DISCRETE_NAIVE_BAYES_CLASSES)
def test_n_features_deprecation(Estimator):
    # Check that we raise the proper deprecation warning if accessing
    # `n_features_`.
    X = np.array([[1, 2], [3, 4]])
    y = np.array([1, 0])
    est = Estimator().fit(X, y)

    with pytest.warns(FutureWarning, match="`n_features_` was deprecated"):
        est.n_features_


def test_cwnb_union():
    # A union of GaussianNB's yields the same prediction a single GaussianNB (fit)
    clf1 = ColumnwiseNB(
        nb_estimators=[("g1", GaussianNB(), [0]), ("g2", GaussianNB(), [1])]
    )
    clf2 = GaussianNB()
    clf1.fit(X, y)
    clf2.fit(X, y)
    assert_array_almost_equal(clf1.predict(X), clf2.predict(X), 8)
    assert_array_almost_equal(clf1.predict_proba(X), clf2.predict_proba(X), 8)
    assert_array_almost_equal(clf1.predict_log_proba(X), clf2.predict_log_proba(X), 8)

    # A union of BernoulliNB's yields the same prediction a single BernoulliNB (fit)
    clf1 = ColumnwiseNB(
        nb_estimators=[("b1", BernoulliNB(), [0]), ("b2", BernoulliNB(), [1, 2])]
    )
    clf2 = BernoulliNB()
    clf1.fit(X1, y1)
    clf2.fit(X1, y1)
    assert_array_almost_equal(clf1.predict_proba(X1), clf2.predict_proba(X1), 8)
    assert_array_almost_equal(clf1.predict_log_proba(X1), clf2.predict_log_proba(X1), 8)
    assert_array_almost_equal(clf1.predict(X1), clf2.predict(X1), 8)

    # A union of BernoulliNB's yields the same prediction a single BernoulliNB
    # (partial_fit)
    clf1 = ColumnwiseNB(
        nb_estimators=[("b1", BernoulliNB(), [0]), ("b2", BernoulliNB(), [1, 2])]
    )
    clf2 = BernoulliNB()
    clf1.partial_fit(X1[:5], y1[:5], classes=[0, 1])
    clf1.partial_fit(X1[5:], y1[5:])
    clf2.fit(X1, y1)
    assert_array_almost_equal(clf1.predict_proba(X1), clf2.predict_proba(X1), 8)
    assert_array_almost_equal(clf1.predict_log_proba(X1), clf2.predict_log_proba(X1), 8)
    assert_array_almost_equal(clf1.predict(X1), clf2.predict(X1), 8)

    # A union of several different NB's is permutation-invariant
    clf1 = ColumnwiseNB(
        nb_estimators=[
            ("b1", BernoulliNB(binarize=2), [3]),
            ("g1", GaussianNB(), [0]),
            ("m1", MultinomialNB(), [0, 2]),
            ("b2", BernoulliNB(), [1]),
        ]
    )
    # permute (0, 1, 2, 3, 4) -> (1, 2, 0, 3, 4) both estimator specs and column numbers
    clf2 = ColumnwiseNB(
        nb_estimators=[
            ("b1", BernoulliNB(binarize=2), [3]),
            ("g1", GaussianNB(), [1]),
            ("m1", MultinomialNB(), [1, 0]),
            ("b2", BernoulliNB(), [2]),
        ]
    )
    clf1.fit(X2[:, [0, 1, 2, 3, 4]], y2)  # (0, 1, 2, 3, 4) -> (1, 2, 0, 3, 4)
    clf2.fit(X2[:, [2, 0, 1, 3, 4]], y2)  # (0, 1, 2, 3, 4) <- (2, 0, 1, 3, 4)
    assert_array_almost_equal(
        clf1.predict_proba(X2), clf2.predict_proba(X2[:, [2, 0, 1, 3, 4]]), 8
    )
    assert_array_almost_equal(
        clf1.predict_log_proba(X2), clf2.predict_log_proba(X2[:, [2, 0, 1, 3, 4]]), 8
    )
    assert_array_almost_equal(clf1.predict(X2), clf2.predict(X2[:, [2, 0, 1, 3, 4]]), 8)


def test_cwnb_estimators_pandas():
    pd = pytest.importorskip("pandas")
    Xdf = pd.DataFrame(data=X, columns=["col0", "col1"])
    ydf = pd.DataFrame({"target": y})

    # Subestimators spec: cols can be lists of int or lists of str, if DataFrame
    clf1 = ColumnwiseNB(
        nb_estimators=[("g1", GaussianNB(), [1]), ("g2", GaussianNB(), [0, 1])]
    )
    clf2 = ColumnwiseNB(
        nb_estimators=[
            ("g1", GaussianNB(), ["col1"]),
            ("g2", GaussianNB(), ["col0", "col1"]),
        ]
    )
    clf1.fit(X, y)
    clf2.fit(Xdf, y)
    assert_array_almost_equal(clf1.predict_log_proba(X), clf2.predict_log_proba(Xdf), 8)
    msg = "A column-vector y was passed when a 1d array was expected"
    with pytest.warns(DataConversionWarning, match=msg):
        clf2.fit(Xdf, ydf)
        assert_array_almost_equal(
            clf1.predict_log_proba(X), clf2.predict_log_proba(Xdf), 8
        )

    # Subestimators spec: empty cols have the same effect as an absent estimator
    # when callable columns produce the empty set.
    select_none = make_column_selector(pattern="qwerasdf")
    clf1 = ColumnwiseNB(
        nb_estimators=[
            ("g1", GaussianNB(), [1]),
            ("g2", GaussianNB(), select_none),
            ("g3", GaussianNB(), [0, 1]),
        ]
    )
    clf2 = ColumnwiseNB(
        nb_estimators=[("g1", GaussianNB(), [1]), ("g3", GaussianNB(), [0, 1])]
    )
    clf1.fit(Xdf, y)
    clf2.fit(Xdf, y)
    assert_array_almost_equal(
        clf1.predict_log_proba(Xdf), clf2.predict_log_proba(Xdf), 8
    )
    # Empty-columns estimators are passed to estimators_ and the numbers match
    assert len(clf1.nb_estimators) == len(clf1.estimators_) == 3
    assert len(clf2.nb_estimators) == len(clf2.estimators_) == 2
    # No cloning of the empty-columns estimators took place:
    assert id(clf1.nb_estimators[1][1]) == id(clf1.named_estimators_["g2"])

    # Subestimators spec: test callable columns
    select_int = make_column_selector(dtype_include=np.int_)
    select_float = make_column_selector(dtype_include=np.float_)
    Xdf2 = Xdf
    Xdf2["col3"] = np.exp(Xdf["col0"]) - 0.5 * Xdf["col1"]
    clf1 = ColumnwiseNB(
        nb_estimators=[
            ("g1", GaussianNB(), ["col3"]),
            ("m1", BernoulliNB(), ["col0", "col1"]),
        ]
    )
    clf2 = ColumnwiseNB(
        nb_estimators=[
            ("g1", GaussianNB(), select_float),
            ("g2", BernoulliNB(), select_int),
        ]
    )
    clf1.fit(Xdf, y)
    clf2.fit(Xdf, y)
    assert_array_almost_equal(
        clf1.predict_log_proba(Xdf), clf2.predict_log_proba(Xdf), 8
    )


def test_cwnb_estimators_1():
    # Subestimators spec: repeated col ints have the same effect as repeating data
    clf1 = ColumnwiseNB(
        nb_estimators=[
            ("g1", GaussianNB(), [1, 1]),
            ("b1", BernoulliNB(), [0, 0, 1, 1]),
        ]
    )
    clf2 = ColumnwiseNB(
        nb_estimators=[
            ("g1", GaussianNB(), [0, 1]),
            ("b1", BernoulliNB(), [2, 3, 4, 5]),
        ]
    )
    clf1.fit(X1, y1)
    clf2.fit(X1[:, [1, 1, 0, 0, 1, 1]], y1)
    assert_array_almost_equal(
        clf1.predict_log_proba(X1), clf2.predict_log_proba(X1[:, [1, 1, 0, 0, 1, 1]]), 8
    )

    # Subestimators spec: empty cols have the same effect as an absent estimator
    clf1 = ColumnwiseNB(
        nb_estimators=[
            ("g1", GaussianNB(), [1]),
            ("g2", GaussianNB(), []),
            ("g3", GaussianNB(), [0, 1]),
        ]
    )
    clf2 = ColumnwiseNB(
        nb_estimators=[("g1", GaussianNB(), [1]), ("g3", GaussianNB(), [0, 1])]
    )
    clf1.fit(X1, y1)
    clf2.fit(X1, y1)
    assert_array_almost_equal(clf1.predict_log_proba(X1), clf2.predict_log_proba(X1), 8)
    # Empty-columns estimators are passed to estimators_ and the numbers match
    assert len(clf1.nb_estimators) == len(clf1.estimators_) == 3
    assert len(clf2.nb_estimators) == len(clf2.estimators_) == 2
    # No cloning of the empty-columns estimators took place:
    assert id(clf1.nb_estimators[1][1]) == id(clf1.named_estimators_["g2"])

    # Subestimators spec: error on repeated names
    clf1 = ColumnwiseNB(
        nb_estimators=[("g1", GaussianNB(), [1]), ("g1", GaussianNB(), [0, 1])]
    )
    msg = "Names provided are not unique"
    with pytest.raises(ValueError, match=msg):
        clf1.fit(X, y)

    clf1 = ColumnwiseNB(
        nb_estimators=[["g1", GaussianNB(), [1]], ["g2", GaussianNB(), [0, 1]]]
    )
    clf1.fit(X, y)


def test_cwnb_estimators_2():
    # Subestimators spec: error on empty list
    clf = ColumnwiseNB(
        nb_estimators=[],
    )
    msg = "A list of naive Bayes estimators must be provided*"
    with pytest.raises(ValueError, match=msg):
        clf.fit(X1, y1)

    # Subestimators spec: error on None
    clf = ColumnwiseNB(
        nb_estimators=None,
    )
    msg = "A list of naive Bayes estimators must be provided*"
    with pytest.raises(ValueError, match=msg):
        clf.fit(X1, y1)

    # Subestimators spec: error when some don't support _joint_log_likelihood
    class notNB(BaseEstimator):
        def __init__(self):
            pass

        def fit(self, X, y):
            pass

        def partial_fit(self, X, y):
            pass

        # def _joint_log_likelihood(self, X): pass
        def predict(self, X):
            pass

    clf1 = ColumnwiseNB(nb_estimators=[["g1", notNB(), [1]], ["g2", GaussianNB(), [0]]])
    msg = "Estimators must be .aive Bayes estimators implementing *"
    with pytest.raises(TypeError, match=msg):
        clf1.partial_fit(X, y)

    # Subestimators spec: error when some don't support fit
    class notNB(BaseEstimator):
        def __init__(self):
            pass

        # def fit(self, X, y): pass
        def partial_fit(self, X, y):
            pass

        def _joint_log_likelihood(self, X):
            pass

        def predict(self, X):
            pass

    clf1 = ColumnwiseNB(nb_estimators=[["g1", notNB(), [1]], ["g2", GaussianNB(), [0]]])
    msg = "Estimators must be .aive Bayes estimators implementing *"
    with pytest.raises(TypeError, match=msg):
        clf1.fit(X, y)

    # Subestimators spec: error when some don't support partial_fit
    class notNB(BaseEstimator):
        def __init__(self):
            pass

        def fit(self, X, y):
            pass

        # def partial_fit(self, X, y): pass
        def _joint_log_likelihood(self, X):
            pass

        def predict(self, X):
            pass

    clf1 = ColumnwiseNB(nb_estimators=[["g1", notNB(), [1]], ["g2", GaussianNB(), [0]]])
    msg = "Estimators must be .aive Bayes estimators implementing *"
    with pytest.raises(TypeError, match=msg):
        clf1.partial_fit(X, y)

    # _estimators setter works
    clf1 = ColumnwiseNB(
        nb_estimators=[("g1", GaussianNB(), [0]), ("b1", BernoulliNB(), [1])]
    )
    clf1.fit(X1, y1)
    clf1._estimators = [
        ("x1", clf1.named_estimators_["g1"]),
        ("x2", clf1.named_estimators_["g1"]),
    ]
    assert clf1.nb_estimators[0][0] == "x1"
    assert clf1.nb_estimators[0][1] is clf1.named_estimators_["g1"]
    assert clf1.nb_estimators[1][0] == "x2"
    assert clf1.nb_estimators[1][1] is clf1.named_estimators_["g1"]


def test_cwnb_prior():
    # prior spec: error when negative, sum!=1 or bad length
    clf1 = ColumnwiseNB(
        nb_estimators=[("g1", GaussianNB(), [1]), ("g2", GaussianNB(), [0, 1])],
        priors=np.array([-0.25, 1.25]),
    )
    msg = "Priors must be non-negative."
    with pytest.raises(ValueError, match=msg):
        clf1.fit(X, y)

    clf1 = ColumnwiseNB(
        nb_estimators=[("g1", GaussianNB(), [1]), ("g2", GaussianNB(), [0, 1])],
        priors=np.array([0.25, 0.7]),
    )
    msg = "The sum of the priors should be 1."
    with pytest.raises(ValueError, match=msg):
        clf1.fit(X, y)

    clf1 = ColumnwiseNB(
        nb_estimators=[("g1", GaussianNB(), [1]), ("g2", GaussianNB(), [0, 1])],
        priors=np.array([0.25, 0.25, 0.25, 0.25]),
    )
    msg = "Number of priors must match number of classes."
    with pytest.raises(ValueError, match=msg):
        clf1.fit(X, y)

    # prior spec: specified prior equals calculated and subestimators' priors
    # prior spec: str prior ties subestimators'
    clf1 = ColumnwiseNB(
        nb_estimators=[
            ("g1", GaussianNB(), [0, 1]),
            ("m1", MultinomialNB(), [2, 3, 4, 5, 6]),
        ],
        priors=np.array([1 / 3, 1 / 3, 1 / 3]),
    )
    clf2a = ColumnwiseNB(
        nb_estimators=[
            ("g1", GaussianNB(), [0, 1]),
            ("m1", MultinomialNB(), [2, 3, 4, 5, 6]),
        ],
        priors="g1",
    )
    clf2b = ColumnwiseNB(
        nb_estimators=[
            ("g1", GaussianNB(), [0, 1]),
            ("m1", MultinomialNB(), [2, 3, 4, 5, 6]),
        ],
        priors="m1",
    )
    clf3 = ColumnwiseNB(
        nb_estimators=[
            ("g1", GaussianNB(), [0, 1]),
            ("m1", MultinomialNB(), [2, 3, 4, 5, 6]),
        ],
    )
    clf1.fit(X2, y2)
    clf2a.fit(X2, y2)
    clf2b.fit(X2, y2)
    clf3.fit(X2, y2)
    assert clf3.priors is None
    assert_array_almost_equal(
        clf1.class_prior_, clf1.named_estimators_["g1"].class_prior_, 8
    )
    assert_array_almost_equal(
        np.log(clf1.class_prior_), clf1.named_estimators_["m1"].class_log_prior_, 8
    )
    assert_array_almost_equal(clf1.class_prior_, clf2a.class_prior_, 8)
    assert_array_almost_equal(clf1.class_prior_, clf2b.class_prior_, 8)
    assert_array_almost_equal(clf1.class_prior_, clf3.class_prior_, 8)

    # prior spec: error message when can't extract prior from subestimator
    class GaussianNB_hide_prior(GaussianNB):
        def fit(self, X, y, sample_weight=None):
            super().fit(X, y, sample_weight=None)
            self.qwerqwer = self.class_prior_
            del self.class_prior_

        def _joint_log_likelihood(self, X):
            self.class_prior_ = self.qwerqwer
            super()._joint_log_likelihood(X)
            del self.class_prior_

    class MultinomialNB_hide_log_prior(MultinomialNB):
        def fit(self, X, y, sample_weight=None):
            super().fit(X, y, sample_weight=None)
            self.qwerqwer = self.class_log_prior_
            del self.class_log_prior_

        def _joint_log_likelihood(self, X):
            self.class_log_prior_ = self.qwerqwer
            super()._joint_log_likelihood(X)
            del self.class_log_prior_

    clf = ColumnwiseNB(
        nb_estimators=[
            ("g1", GaussianNB(), [1]),
            ("g2", GaussianNB_hide_prior(), [0, 1]),
        ],
        priors="g2",
    )
    msg = "Unable to extract class prior from estimator g2*"
    with pytest.raises(AttributeError, match=msg):
        clf.fit(X, y)

    clf = ColumnwiseNB(
        nb_estimators=[
            ("g1", GaussianNB(), [0]),
            ("m1", MultinomialNB_hide_log_prior(), [1, 2, 3, 4, 5]),
        ],
        priors="m1",
    )
    msg = "Unable to extract class prior from estimator m1*"
    with pytest.raises(AttributeError, match=msg):
        clf.fit(X2, y2)


def test_cwnb_zero_prior():
    # P(y)=0 in a subestimator results in P(y|x)=0 of meta-estimator
    clf1 = ColumnwiseNB(
        nb_estimators=[
            ("g1", GaussianNB(), [1, 3, 5]),
            ("g2", GaussianNB(priors=np.array([0.5, 0, 0.5])), [0, 1]),
        ]
    )
    clf1.fit(X2, y2)
    msg = "divide by zero encountered in log"
    with pytest.warns(RuntimeWarning, match=msg):
        p = clf1.predict_proba(X2)[:, 1]
    assert_almost_equal(np.abs(p).sum(), 0)
    assert np.isfinite(p).all()
    Xt = rng.randint(5, size=(6, 100))
    with pytest.warns(RuntimeWarning, match=msg):
        p = clf1.predict_proba(Xt)[:, 1]
    assert_almost_equal(np.abs(p).sum(), 0)
    assert np.isfinite(p).all()

    # P(y)=0 in the meta-estimator, as well as class priors that differ across
    # subestimators may produce meaningless results, including NaNs. This case
    # is not tested here.

    # P(y)=0 in two subestimators results in P(y|x)=0 of meta-estimator
    clf1 = ColumnwiseNB(
        nb_estimators=[
            ("g1", GaussianNB(priors=np.array([0.6, 0, 0.4])), [1, 3, 5]),
            ("g2", GaussianNB(priors=np.array([0.5, 0, 0.5])), [0, 1]),
        ]
    )
    clf1.fit(X2, y2)
    with pytest.warns(RuntimeWarning, match=msg):
        p = clf1.predict_proba(X2)[:, 1]
    assert_almost_equal(np.abs(p).sum(), 0)
    assert np.isfinite(p).all()
    Xt = rng.randint(5, size=(6, 100))
    with pytest.warns(RuntimeWarning, match=msg):
        p = clf1.predict_proba(Xt)[:, 1]
    assert_almost_equal(np.abs(p).sum(), 0)
    assert np.isfinite(p).all()


def test_cwnb_sample_weight():
    # weights in fit have no effect if all ones
    weights = [1, 1, 1, 1, 1, 1]
    clf1 = ColumnwiseNB(
        nb_estimators=[("g1", GaussianNB(), [1]), ("g2", GaussianNB(), [0, 1])]
    )
    clf2 = ColumnwiseNB(
        nb_estimators=[("g1", GaussianNB(), [1]), ("g2", GaussianNB(), [0, 1])]
    )
    clf1.fit(X, y, sample_weight=weights)
    clf2.fit(X, y)
    assert_array_almost_equal(
        clf1._joint_log_likelihood(X), clf2._joint_log_likelihood(X), 8
    )
    assert_array_almost_equal(clf1.predict_log_proba(X), clf2.predict_log_proba(X), 8)
    assert_array_equal(clf1.predict(X), clf2.predict(X))

    # weights in partial_fit have no effect if all ones
    clf1 = ColumnwiseNB(
        nb_estimators=[
            ("b1", BernoulliNB(binarize=2), [1]),
            ("m1", MultinomialNB(), [0, 2, 3]),
        ]
    )
    clf2 = ColumnwiseNB(
        nb_estimators=[
            ("b1", BernoulliNB(binarize=2), [1]),
            ("m1", MultinomialNB(), [0, 2, 3]),
        ]
    )
    clf1.partial_fit(X2, y2, sample_weight=weights, classes=np.unique(y2))
    clf2.partial_fit(X2, y2, classes=np.unique(y2))
    assert_array_almost_equal(
        clf1._joint_log_likelihood(X2), clf2._joint_log_likelihood(X2), 8
    )
    assert_array_almost_equal(clf1.predict_log_proba(X2), clf2.predict_log_proba(X2), 8)
    assert_array_equal(clf1.predict(X2), clf2.predict(X2))

    # weights in fit have the same effect as repeating data
    weights = [1, 2, 3, 1, 4, 2]
    idx = list(chain(*([i] * w for i, w in enumerate(weights))))
    # var_smoothing=0.0 is for maximum precision in dealing with a small sample
    clf1 = ColumnwiseNB(
        nb_estimators=[
            ("g1", GaussianNB(var_smoothing=0.0), [1]),
            ("g2", GaussianNB(var_smoothing=0.0), [0, 1]),
        ]
    )
    clf2 = ColumnwiseNB(
        nb_estimators=[
            ("g1", GaussianNB(var_smoothing=0.0), [1]),
            ("g2", GaussianNB(var_smoothing=0.0), [0, 1]),
        ]
    )
    clf1.fit(X, y, sample_weight=weights)
    clf2.fit(X[idx], y[idx])
    assert_array_almost_equal(
        clf1._joint_log_likelihood(X), clf2._joint_log_likelihood(X), 8
    )
    assert_array_almost_equal(clf1.predict_log_proba(X), clf2.predict_log_proba(X), 8)
    assert_array_equal(clf1.predict(X), clf2.predict(X), 8)
    for attr_name in ("class_count_", "class_prior_", "classes_"):
        assert_array_equal(getattr(clf1, attr_name), getattr(clf1, attr_name))

    # weights in partial_fit have the same effect as repeating data
    clf1 = ColumnwiseNB(
        nb_estimators=[
            ("b1", BernoulliNB(binarize=2), [1]),
            ("m1", MultinomialNB(), [0, 2, 3]),
        ]
    )
    clf2 = ColumnwiseNB(
        nb_estimators=[
            ("b1", BernoulliNB(binarize=2), [1]),
            ("m1", MultinomialNB(), [0, 2, 3]),
        ]
    )
    clf1.partial_fit(X2, y2, sample_weight=weights, classes=np.unique(y2))
    clf2.partial_fit(X2[idx], y2[idx], classes=np.unique(y2))
    assert_array_equal(clf1._joint_log_likelihood(X2), clf2._joint_log_likelihood(X2))
    assert_array_equal(clf1.predict_log_proba(X2), clf2.predict_log_proba(X2))
    assert_array_equal(clf1.predict(X2), clf2.predict(X2))
    for attr_name in ("class_count_", "class_prior_", "classes_"):
        assert_array_equal(getattr(clf1, attr_name), getattr(clf1, attr_name))


def test_cwnb_partial_fit():
    # partial_fit: consecutive calls yield the same prediction as a single call
    clf1 = ColumnwiseNB(
        nb_estimators=[("b1", BernoulliNB(), [1]), ("m1", MultinomialNB(), [0, 2, 3])]
    )
    clf2 = ColumnwiseNB(
        nb_estimators=[("b1", BernoulliNB(), [1]), ("m1", MultinomialNB(), [0, 2, 3])]
    )
    clf1.partial_fit(X2, y2, classes=np.unique(y2))
    clf2.partial_fit(X2[:4], y2[:4], classes=np.unique(y2))
    clf2.partial_fit(X2[4:], y2[4:])
    assert_array_almost_equal(
        clf1._joint_log_likelihood(X2), clf2._joint_log_likelihood(X2), 8
    )
    assert_array_almost_equal(clf1.predict_log_proba(X2), clf2.predict_log_proba(X2), 8)
    assert_array_equal(clf1.predict(X2), clf2.predict(X2))
    for attr_name in ("class_count_", "class_prior_", "classes_"):
        assert_array_equal(getattr(clf1, attr_name), getattr(clf1, attr_name))

    # partial_fit: error when classes are not provided at the first call
    clf1 = ColumnwiseNB(
        nb_estimators=[("b1", BernoulliNB(), [1]), ("m1", MultinomialNB(), [0, 2, 3])]
    )
    msg = ".lasses must be passed on the first call to partial_fit"
    with pytest.raises(ValueError, match=msg):
        clf1.partial_fit(X2, y2)


def test_cwnb_consistency():
    # class_count_, classes_, class_prior_ are consistent in meta-, sub-estimators
    clf1 = ColumnwiseNB(
        nb_estimators=[
            ("b1", BernoulliNB(binarize=2), [1]),
            ("m1", MultinomialNB(), [0, 2, 3]),
        ]
    )
    clf1.fit(X2, y2)
    for se in clf1.named_estimators_:
        assert_array_almost_equal(
            clf1.class_count_, clf1.named_estimators_[se].class_count_, 8
        )
        assert_array_almost_equal(clf1.classes_, clf1.named_estimators_[se].classes_, 8)
        assert_array_almost_equal(
            np.log(clf1.class_prior_), clf1.named_estimators_[se].class_log_prior_, 8
        )


def test_cwnb_params():
    # Can get and set subestimators' parameters through name__paramname
    # clone() works on ColumnwiseNB
    clf1 = ColumnwiseNB(
        nb_estimators=[
            ("b1", BernoulliNB(alpha=0.2, binarize=2), [1]),
            ("m1", MultinomialNB(class_prior=[0.2, 0.2, 0.6]), [0, 2, 3]),
        ]
    )
    clf1.fit(X2, y2)
    p = clf1.get_params(deep=True)
    assert p["b1__alpha"] == 0.2
    assert p["b1__binarize"] == 2
    assert p["m1__class_prior"] == [0.2, 0.2, 0.6]
    clf1.set_params(b1__alpha=123, m1__class_prior=[0.3, 0.3, 0.4])
    assert clf1.nb_estimators[0][1].alpha == 123
    assert_array_equal(clf1.nb_estimators[1][1].class_prior, [0.3, 0.3, 0.4])
    # After cloning and fitting, we can check through named_estimators, which
    # maps to fitted estimators_:
    clf2 = clone(clf1).fit(X2, y2)
    assert clf2.named_estimators_["b1"].alpha == 123
    assert_array_equal(clf2.named_estimators_["m1"].class_prior, [0.3, 0.3, 0.4])
    assert id(clf2.named_estimators_["b1"]) != id(clf1.named_estimators_["b1"])


def test_cwnb_n_jobs():
    # n_jobs: same results wether with it or without
    clf1 = ColumnwiseNB(
        nb_estimators=[
            ("b1", BernoulliNB(binarize=2), [1]),
            ("b2", BernoulliNB(binarize=2), [1]),
            ("m1", MultinomialNB(), [0, 2, 3]),
            ("m3", MultinomialNB(), slice(10, None)),
        ],
        n_jobs=4,
    )
    clf2 = ColumnwiseNB(
        nb_estimators=[
            ("b1", BernoulliNB(binarize=2), [1]),
            ("b2", BernoulliNB(binarize=2), [1]),
            ("m1", MultinomialNB(), [0, 2, 3]),
            ("m3", MultinomialNB(), slice(10, None)),
        ]
    )
    clf1.partial_fit(X2, y2, classes=np.unique(y2))
    clf2.partial_fit(X2, y2, classes=np.unique(y2))

    assert_array_almost_equal(
        clf1._joint_log_likelihood(X2), clf2._joint_log_likelihood(X2), 8
    )
    assert_array_almost_equal(clf1.predict_log_proba(X2), clf2.predict_log_proba(X2), 8)
    assert_array_equal(clf1.predict(X2), clf2.predict(X2))


def test_cwnb_example():
    # Test the Example from ColumnwiseNB docstring in naive_bayes.py
    import numpy as np

    rng = np.random.RandomState(1)
    X = rng.randint(5, size=(6, 100))
    y = np.array([0, 0, 1, 1, 2, 2])
    from sklearn.naive_bayes import MultinomialNB, GaussianNB, ColumnwiseNB

    clf = ColumnwiseNB(
        nb_estimators=[
            ("mnb1", MultinomialNB(), [0, 1]),
            ("mnb2", MultinomialNB(), [3, 4]),
            ("gnb1", GaussianNB(), [5]),
        ]
    )
    clf.fit(X, y)
    clf.predict(X)


def test_cwnb_verbose(capsys):
    # Setting verbose=True does not result in an error.
    # This DOES NOT test if the desired output is generated.
    clf = ColumnwiseNB(
        nb_estimators=[
            ("mnb1", MultinomialNB(), [0, 1]),
            ("mnb2", MultinomialNB(), [3, 4]),
            ("gnb1", GaussianNB(), [5]),
        ],
        verbose=True,
        n_jobs=4,
    )
    clf.fit(X2, y2)
    clf.predict(X2)


def test_cwnb_sk_visual_block(capsys):
    # Setting verbose=True does not result in an error.
    # This DOES NOT test if the desired output is generated.
    estimators = (MultinomialNB(), MultinomialNB(), GaussianNB())
    clf = ColumnwiseNB(
        nb_estimators=[
            ("mnb1", estimators[0], [0, 1]),
            ("mnb2", estimators[1], [3, 4]),
            ("gnb1", estimators[2], [5]),
        ],
        verbose=True,
        n_jobs=4,
    )
    visual_block = clf._sk_visual_block_()
    assert visual_block.names == ('mnb1', 'mnb2', 'gnb1')
    assert visual_block.name_details == ([0, 1], [3, 4], [5])
    assert visual_block.estimators == estimators
