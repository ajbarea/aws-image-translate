import json
import os
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from lambda_functions import history_handler


@pytest.fixture
def mock_event():
    """Mock API Gateway event with authentication"""
    return {
        "requestContext": {"authorizer": {"jwt": {"claims": {"sub": "test-user-123"}}}},
        "pathParameters": None,
    }


@pytest.fixture
def mock_event_with_history_id():
    """Mock API Gateway event with history_id path parameter"""
    return {
        "requestContext": {"authorizer": {"jwt": {"claims": {"sub": "test-user-123"}}}},
        "pathParameters": {"history_id": "hist-456"},
    }


@pytest.fixture
def mock_event_unauthorized():
    """Mock API Gateway event without authentication"""
    return {"requestContext": {}, "pathParameters": None}


@pytest.fixture
def mock_history_items():
    """Mock DynamoDB query response for history items"""
    return {
        "Items": [
            {
                "history_id": "hist-123",
                "image_key": "test-image-1.jpg",
                "lang_pair": "en#es",
                "timestamp": "2024-01-15T10:30:00Z",
            },
            {
                "history_id": "hist-124",
                "image_key": "test-image-2.jpg",
                "lang_pair": "fr#en",
                "timestamp": "2024-01-14T15:45:00Z",
            },
        ]
    }


@pytest.fixture
def mock_history_item():
    """Mock DynamoDB get_item response for single history item"""
    return {
        "Item": {
            "history_id": "hist-456",
            "translation_id": "trans-789",
            "image_key": "detailed-image.jpg",
            "lang_pair": "de#en",
            "timestamp": "2024-01-16T12:00:00Z",
        }
    }


@pytest.fixture
def mock_translation_item():
    """Mock DynamoDB get_item response for translation details"""
    return {
        "Item": {
            "translation_id": "trans-789",
            "extracted_text": "Hallo Welt",
            "translated_text": "Hello World",
            "image_key": "detailed-image.jpg",
            "lang_pair": "de#en",
            "timestamp": "2024-01-16T12:00:00Z",
        }
    }


class TestListHistory:
    """Tests for the list_history function"""

    @patch("lambda_functions.history_handler.get_history_table")
    def test_list_history_success(self, mock_get_table, mock_event, mock_history_items):
        """Test successful history listing"""
        mock_table = MagicMock()
        mock_get_table.return_value = mock_table
        mock_table.query.return_value = mock_history_items

        result = history_handler.list_history(mock_event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["user_id"] == "test-user-123"
        assert len(body["history"]) == 2

        # Check first item structure
        first_item = body["history"][0]
        assert first_item["history_id"] == "hist-123"
        assert first_item["image_name"] == "test-image-1.jpg"
        assert first_item["src_lang"] == "en"
        assert first_item["t_lang"] == "es"
        assert first_item["created_on"] == "2024-01-15T10:30:00Z"

    @patch("lambda_functions.history_handler.get_history_table")
    def test_list_history_unauthorized(self, mock_get_table, mock_event_unauthorized):
        """Test history listing without authentication"""
        result = history_handler.list_history(mock_event_unauthorized, None)

        assert result["statusCode"] == 401
        body = json.loads(result["body"])
        assert body["error"] == "Unauthorized"
        mock_get_table.assert_not_called()

    @patch("lambda_functions.history_handler.get_history_table")
    def test_list_history_empty_results(self, mock_get_table, mock_event):
        """Test history listing with no items"""
        mock_table = MagicMock()
        mock_get_table.return_value = mock_table
        mock_table.query.return_value = {"Items": []}

        result = history_handler.list_history(mock_event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["user_id"] == "test-user-123"
        assert body["history"] == []

    @patch("lambda_functions.history_handler.get_history_table")
    def test_list_history_database_error(self, mock_get_table, mock_event):
        """Test history listing with database error"""
        mock_table = MagicMock()
        mock_get_table.return_value = mock_table
        mock_table.query.side_effect = Exception("DynamoDB error")

        # The function doesn't have explicit error handling, so it should raise
        with pytest.raises(Exception):
            history_handler.list_history(mock_event, None)


class TestGetHistoryItem:
    """Tests for the get_history_item function"""

    @patch("lambda_functions.history_handler.get_translations_table")
    @patch("lambda_functions.history_handler.get_history_table")
    def test_get_history_item_success(
        self,
        mock_get_history_table,
        mock_get_trans_table,
        mock_event_with_history_id,
        mock_history_item,
        mock_translation_item,
    ):
        """Test successful history item retrieval"""
        mock_history_table = MagicMock()
        mock_trans_table = MagicMock()
        mock_get_history_table.return_value = mock_history_table
        mock_get_trans_table.return_value = mock_trans_table
        mock_history_table.get_item.return_value = mock_history_item
        mock_trans_table.get_item.return_value = mock_translation_item

        result = history_handler.get_history_item(mock_event_with_history_id, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["history_id"] == "hist-456"
        assert body["image_name"] == "detailed-image.jpg"
        assert body["src_lang"] == "de"
        assert body["src_text"] == "Hallo Welt"
        assert body["t_lang"] == "en"
        assert body["t_text"] == "Hello World"

    @patch("lambda_functions.history_handler.get_history_table")
    def test_get_history_item_unauthorized(
        self, mock_get_table, mock_event_unauthorized
    ):
        """Test history item retrieval without authentication"""
        mock_event_unauthorized["pathParameters"] = {"history_id": "hist-456"}

        result = history_handler.get_history_item(mock_event_unauthorized, None)

        assert result["statusCode"] == 401
        body = json.loads(result["body"])
        assert body["error"] == "Unauthorized"
        mock_get_table.assert_not_called()

    @patch("lambda_functions.history_handler.get_history_table")
    def test_get_history_item_missing_history_id(self, mock_get_table, mock_event):
        """Test history item retrieval without history_id parameter"""
        result = history_handler.get_history_item(mock_event, None)

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["error"] == "Missing history_id in path"
        mock_get_table.assert_not_called()

    @patch("lambda_functions.history_handler.get_history_table")
    def test_get_history_item_not_found(
        self, mock_get_table, mock_event_with_history_id
    ):
        """Test history item retrieval when item doesn't exist"""
        mock_table = MagicMock()
        mock_get_table.return_value = mock_table
        mock_table.get_item.return_value = {}

        result = history_handler.get_history_item(mock_event_with_history_id, None)

        assert result["statusCode"] == 404
        body = json.loads(result["body"])
        assert body["error"] == "History record not found"

    @patch("lambda_functions.history_handler.get_translations_table")
    @patch("lambda_functions.history_handler.get_history_table")
    def test_get_history_item_translation_missing(
        self,
        mock_get_history_table,
        mock_get_trans_table,
        mock_event_with_history_id,
        mock_history_item,
    ):
        """Test history item retrieval when translation record is missing"""
        mock_history_table = MagicMock()
        mock_trans_table = MagicMock()
        mock_get_history_table.return_value = mock_history_table
        mock_get_trans_table.return_value = mock_trans_table
        mock_history_table.get_item.return_value = mock_history_item
        mock_trans_table.get_item.return_value = {}

        result = history_handler.get_history_item(mock_event_with_history_id, None)

        assert result["statusCode"] == 502
        body = json.loads(result["body"])
        assert body["error"] == "Translation record missing"


class TestGetUserId:
    """Tests for the _get_user_id helper function"""

    def test_get_user_id_success(self):
        """Test successful user ID extraction"""
        event = {
            "requestContext": {
                "authorizer": {"jwt": {"claims": {"sub": "test-user-456"}}}
            }
        }

        user_id = history_handler._get_user_id(event)
        assert user_id == "test-user-456"

    def test_get_user_id_missing_context(self):
        """Test user ID extraction with missing request context"""
        event = {}

        user_id = history_handler._get_user_id(event)
        assert user_id is None

    def test_get_user_id_missing_claims(self):
        """Test user ID extraction with missing claims"""
        event = {"requestContext": {"authorizer": {"jwt": {}}}}

        user_id = history_handler._get_user_id(event)
        assert user_id is None

    def test_get_user_id_missing_sub(self):
        """Test user ID extraction with missing sub claim"""
        event = {"requestContext": {"authorizer": {"jwt": {"claims": {}}}}}

        user_id = history_handler._get_user_id(event)
        assert user_id is None

    def test_get_user_id_fallback_cognito_username(self):
        """Test user ID extraction with cognito:username fallback"""
        event = {
            "requestContext": {
                "authorizer": {
                    "jwt": {"claims": {"cognito:username": "test-cognito-user"}}
                }
            }
        }

        user_id = history_handler._get_user_id(event)
        assert user_id == "test-cognito-user"

    def test_get_user_id_fallback_username(self):
        """Test user ID extraction with username fallback"""
        event = {
            "requestContext": {
                "authorizer": {"jwt": {"claims": {"username": "test-username"}}}
            }
        }

        user_id = history_handler._get_user_id(event)
        assert user_id == "test-username"

    def test_get_user_id_fallback_email(self):
        """Test user ID extraction with email fallback"""
        event = {
            "requestContext": {
                "authorizer": {"jwt": {"claims": {"email": "test@example.com"}}}
            }
        }

        user_id = history_handler._get_user_id(event)
        assert user_id == "test@example.com"


class TestDynamoDBInitialization:
    """Tests for DynamoDB initialization functions"""

    @patch("lambda_functions.history_handler.boto3.resource")
    @patch.dict(os.environ, {"AWS_REGION": "us-east-1"})
    def test_get_dynamodb_first_call(self, mock_boto3_resource):
        """Test first call to _get_dynamodb initializes the resource"""
        # Reset the global variable to simulate first call
        history_handler._dynamodb = None

        mock_resource = MagicMock()
        mock_boto3_resource.return_value = mock_resource

        result = history_handler._get_dynamodb()

        mock_boto3_resource.assert_called_once_with("dynamodb", region_name="us-east-1")
        assert result == mock_resource
        assert history_handler._dynamodb == mock_resource

    @patch("lambda_functions.history_handler.boto3.resource")
    def test_get_dynamodb_subsequent_call(self, mock_boto3_resource):
        """Test subsequent calls to _get_dynamodb return cached resource"""
        # Set up cached resource
        cached_resource = MagicMock()
        history_handler._dynamodb = cached_resource

        result = history_handler._get_dynamodb()

        # Should not call boto3.resource again
        mock_boto3_resource.assert_not_called()
        assert result == cached_resource

    @patch.dict(os.environ, {}, clear=True)
    @patch("lambda_functions.history_handler.boto3.resource")
    def test_get_dynamodb_no_region(self, mock_boto3_resource):
        """Test _get_dynamodb with no AWS_REGION environment variable"""
        history_handler._dynamodb = None
        mock_resource = MagicMock()
        mock_boto3_resource.return_value = mock_resource

        result = history_handler._get_dynamodb()

        # Should call with None region when env var not set
        mock_boto3_resource.assert_called_once_with("dynamodb", region_name=None)
        assert result == mock_resource


class TestHistoryTableInitialization:
    """Tests for history table initialization functions"""

    @patch("lambda_functions.history_handler._get_dynamodb")
    @patch.dict(os.environ, {"TRANSLATION_HISTORY_TABLE": "test-history-table"})
    def test_get_history_table_first_call(self, mock_get_dynamodb):
        """Test first call to _get_history_table initializes the table"""
        # Reset the global variable
        history_handler._history_table = None

        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_get_dynamodb.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table

        result = history_handler._get_history_table()

        mock_get_dynamodb.assert_called_once()
        mock_dynamodb.Table.assert_called_once_with("test-history-table")
        assert result == mock_table
        assert history_handler._history_table == mock_table

    @patch("lambda_functions.history_handler._get_dynamodb")
    def test_get_history_table_subsequent_call(self, mock_get_dynamodb):
        """Test subsequent calls to _get_history_table return cached table"""
        # Set up cached table
        cached_table = MagicMock()
        history_handler._history_table = cached_table

        result = history_handler._get_history_table()

        # Should not call _get_dynamodb again
        mock_get_dynamodb.assert_not_called()
        assert result == cached_table

    @patch.dict(os.environ, {}, clear=True)
    def test_get_history_table_no_env_var(self):
        """Test _get_history_table raises error when environment variable not set"""
        history_handler._history_table = None

        with pytest.raises(
            ValueError, match="TRANSLATION_HISTORY_TABLE environment variable not set"
        ):
            history_handler._get_history_table()

    @patch.dict(os.environ, {"TRANSLATION_HISTORY_TABLE": ""})
    def test_get_history_table_empty_env_var(self):
        """Test _get_history_table raises error when environment variable is empty"""
        history_handler._history_table = None

        with pytest.raises(
            ValueError, match="TRANSLATION_HISTORY_TABLE environment variable not set"
        ):
            history_handler._get_history_table()


class TestTranslationsTableInitialization:
    """Tests for translations table initialization functions"""

    @patch("lambda_functions.history_handler._get_dynamodb")
    @patch.dict(os.environ, {"TRANSLATIONS_TABLE": "test-translations-table"})
    def test_get_translations_table_first_call(self, mock_get_dynamodb):
        """Test first call to _get_translations_table initializes the table"""
        # Reset the global variable
        history_handler._translations_table = None

        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_get_dynamodb.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table

        result = history_handler._get_translations_table()

        mock_get_dynamodb.assert_called_once()
        mock_dynamodb.Table.assert_called_once_with("test-translations-table")
        assert result == mock_table
        assert history_handler._translations_table == mock_table

    @patch("lambda_functions.history_handler._get_dynamodb")
    def test_get_translations_table_subsequent_call(self, mock_get_dynamodb):
        """Test subsequent calls to _get_translations_table return cached table"""
        # Set up cached table
        cached_table = MagicMock()
        history_handler._translations_table = cached_table

        result = history_handler._get_translations_table()

        # Should not call _get_dynamodb again
        mock_get_dynamodb.assert_not_called()
        assert result == cached_table

    @patch.dict(os.environ, {}, clear=True)
    def test_get_translations_table_no_env_var(self):
        """Test _get_translations_table raises error when environment variable not set"""
        history_handler._translations_table = None

        with pytest.raises(
            ValueError, match="TRANSLATIONS_TABLE environment variable not set"
        ):
            history_handler._get_translations_table()

    @patch.dict(os.environ, {"TRANSLATIONS_TABLE": ""})
    def test_get_translations_table_empty_env_var(self):
        """Test _get_translations_table raises error when environment variable is empty"""
        history_handler._translations_table = None

        with pytest.raises(
            ValueError, match="TRANSLATIONS_TABLE environment variable not set"
        ):
            history_handler._get_translations_table()


class TestPublicHelperFunctions:
    """Tests for public helper functions"""

    @patch("lambda_functions.history_handler._get_history_table")
    def test_get_history_table_wrapper(self, mock_get_history_table):
        """Test public get_history_table function calls private version"""
        mock_table = MagicMock()
        mock_get_history_table.return_value = mock_table

        result = history_handler.get_history_table()

        mock_get_history_table.assert_called_once()
        assert result == mock_table

    @patch("lambda_functions.history_handler._get_translations_table")
    def test_get_translations_table_wrapper(self, mock_get_translations_table):
        """Test public get_translations_table function calls private version"""
        mock_table = MagicMock()
        mock_get_translations_table.return_value = mock_table

        result = history_handler.get_translations_table()

        mock_get_translations_table.assert_called_once()
        assert result == mock_table


class TestLangPairParsing:
    """Tests for language pair parsing in different scenarios"""

    @patch("lambda_functions.history_handler.get_history_table")
    def test_list_history_complex_lang_pairs(self, mock_get_table, mock_event):
        """Test language pair parsing with complex language codes"""
        mock_table = MagicMock()
        mock_get_table.return_value = mock_table

        # Test with complex language pairs that might have multiple # characters
        mock_history_items = {
            "Items": [
                {
                    "history_id": "hist-123",
                    "image_key": "test-image.jpg",
                    "lang_pair": "zh-CN#en-US",  # Complex language codes
                    "timestamp": "2024-01-15T10:30:00Z",
                },
                {
                    "history_id": "hist-124",
                    "image_key": "test-image-2.jpg",
                    "lang_pair": "pt-BR#es-ES",  # Another complex pair
                    "timestamp": "2024-01-14T15:45:00Z",
                },
            ]
        }
        mock_table.query.return_value = mock_history_items

        result = history_handler.list_history(mock_event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert len(body["history"]) == 2

        # Check complex language pair parsing
        first_item = body["history"][0]
        assert first_item["src_lang"] == "zh-CN"
        assert first_item["t_lang"] == "en-US"

        second_item = body["history"][1]
        assert second_item["src_lang"] == "pt-BR"
        assert second_item["t_lang"] == "es-ES"

    @patch("lambda_functions.history_handler.get_history_table")
    @patch("lambda_functions.history_handler.get_translations_table")
    def test_get_history_item_complex_lang_pair(
        self, mock_get_trans_table, mock_get_history_table, mock_event_with_history_id
    ):
        """Test get_history_item with complex language pair"""
        mock_history_table = MagicMock()
        mock_trans_table = MagicMock()
        mock_get_history_table.return_value = mock_history_table
        mock_get_trans_table.return_value = mock_trans_table

        # History item with complex language pair
        mock_history_item = {
            "Item": {
                "history_id": "hist-456",
                "translation_id": "trans-789",
                "image_key": "detailed-image.jpg",
                "lang_pair": "ja-JP#en-GB",  # Japanese to British English
                "timestamp": "2024-01-16T12:00:00Z",
            }
        }

        mock_translation_item = {
            "Item": {
                "translation_id": "trans-789",
                "extracted_text": "こんにちは",
                "translated_text": "Hello",
                "image_key": "detailed-image.jpg",
                "lang_pair": "ja-JP#en-GB",
                "timestamp": "2024-01-16T12:00:00Z",
            }
        }

        mock_history_table.get_item.return_value = mock_history_item
        mock_trans_table.get_item.return_value = mock_translation_item

        result = history_handler.get_history_item(mock_event_with_history_id, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["src_lang"] == "ja-JP"
        assert body["t_lang"] == "en-GB"
        assert body["src_text"] == "こんにちは"
        assert body["t_text"] == "Hello"


class TestErrorHandling:
    """Tests for error conditions in initialization"""

    @patch("lambda_functions.history_handler.boto3.resource")
    @patch.dict(os.environ, {"AWS_REGION": "us-east-1"})
    def test_boto3_resource_failure(self, mock_boto3_resource):
        """Test handling of boto3 resource creation failure"""
        history_handler._dynamodb = None
        mock_boto3_resource.side_effect = Exception("AWS credentials not found")

        with pytest.raises(Exception, match="AWS credentials not found"):
            history_handler._get_dynamodb()

    @patch("lambda_functions.history_handler._get_dynamodb")
    @patch.dict(os.environ, {"TRANSLATION_HISTORY_TABLE": "test-table"})
    def test_table_creation_failure(self, mock_get_dynamodb):
        """Test handling of table creation failure"""
        history_handler._history_table = None

        mock_dynamodb = MagicMock()
        mock_get_dynamodb.return_value = mock_dynamodb
        mock_dynamodb.Table.side_effect = Exception("Table not found")

        with pytest.raises(Exception, match="Table not found"):
            history_handler._get_history_table()


class TestMissingTranslationFields:
    """Tests for handling missing fields in translation records"""

    @patch("lambda_functions.history_handler.get_translations_table")
    @patch("lambda_functions.history_handler.get_history_table")
    def test_get_history_item_missing_extracted_text(
        self, mock_get_history_table, mock_get_trans_table, mock_event_with_history_id
    ):
        """Test handling when extracted_text is missing from translation record"""
        mock_history_table = MagicMock()
        mock_trans_table = MagicMock()
        mock_get_history_table.return_value = mock_history_table
        mock_get_trans_table.return_value = mock_trans_table

        mock_history_item = {
            "Item": {
                "history_id": "hist-456",
                "translation_id": "trans-789",
                "image_key": "detailed-image.jpg",
                "lang_pair": "de#en",
                "timestamp": "2024-01-16T12:00:00Z",
            }
        }

        # Translation item missing extracted_text
        mock_translation_item = {
            "Item": {
                "translation_id": "trans-789",
                "translated_text": "Hello World",
                "image_key": "detailed-image.jpg",
                "lang_pair": "de#en",
                "timestamp": "2024-01-16T12:00:00Z",
                # extracted_text is missing
            }
        }

        mock_history_table.get_item.return_value = mock_history_item
        mock_trans_table.get_item.return_value = mock_translation_item

        result = history_handler.get_history_item(mock_event_with_history_id, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["src_text"] == ""  # Should default to empty string
        assert body["t_text"] == "Hello World"

    @patch("lambda_functions.history_handler.get_translations_table")
    @patch("lambda_functions.history_handler.get_history_table")
    def test_get_history_item_missing_translated_text(
        self, mock_get_history_table, mock_get_trans_table, mock_event_with_history_id
    ):
        """Test handling when translated_text is missing from translation record"""
        mock_history_table = MagicMock()
        mock_trans_table = MagicMock()
        mock_get_history_table.return_value = mock_history_table
        mock_get_trans_table.return_value = mock_trans_table

        mock_history_item = {
            "Item": {
                "history_id": "hist-456",
                "translation_id": "trans-789",
                "image_key": "detailed-image.jpg",
                "lang_pair": "de#en",
                "timestamp": "2024-01-16T12:00:00Z",
            }
        }

        # Translation item missing translated_text
        mock_translation_item = {
            "Item": {
                "translation_id": "trans-789",
                "extracted_text": "Hallo Welt",
                "image_key": "detailed-image.jpg",
                "lang_pair": "de#en",
                "timestamp": "2024-01-16T12:00:00Z",
                # translated_text is missing
            }
        }

        mock_history_table.get_item.return_value = mock_history_item
        mock_trans_table.get_item.return_value = mock_translation_item

        result = history_handler.get_history_item(mock_event_with_history_id, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["src_text"] == "Hallo Welt"
        assert body["t_text"] == ""  # Should default to empty string


class TestIntegrationWithMoto:
    """Integration tests using moto for actual DynamoDB simulation"""

    @mock_aws
    @patch.dict(
        os.environ,
        {
            "AWS_REGION": "us-east-1",
            "TRANSLATION_HISTORY_TABLE": "test-history",
            "TRANSLATIONS_TABLE": "test-translations",
        },
    )
    def test_full_initialization_chain(self):
        """Test full initialization chain with moto"""
        # Reset global variables
        history_handler._dynamodb = None
        history_handler._history_table = None
        history_handler._translations_table = None

        # Create tables in moto
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        # Create history table
        dynamodb.create_table(
            TableName="test-history",
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "history_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "history_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create translations table
        dynamodb.create_table(
            TableName="test-translations",
            KeySchema=[{"AttributeName": "translation_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "translation_id", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Test that our functions can initialize and work with real DynamoDB
        history_table_result = history_handler.get_history_table()
        translations_table_result = history_handler.get_translations_table()

        assert history_table_result.table_name == "test-history"
        assert translations_table_result.table_name == "test-translations"

        # Test that subsequent calls return the same objects
        assert history_handler.get_history_table() is history_table_result
        assert history_handler.get_translations_table() is translations_table_result


@pytest.fixture(autouse=True)
def reset_global_variables():
    """Reset global variables before each test to ensure isolation"""
    original_dynamodb = history_handler._dynamodb
    original_history_table = history_handler._history_table
    original_translations_table = history_handler._translations_table

    yield

    # Reset to original values after test
    history_handler._dynamodb = original_dynamodb
    history_handler._history_table = original_history_table
    history_handler._translations_table = original_translations_table


if __name__ == "__main__":  # pragma: no cover
    pytest.main(["-v", "tests/test_history_handler.py"])
