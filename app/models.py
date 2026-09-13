"""Validated domain models for the Smartshop catalog and policy datasets.

The models in this module define the typed application boundary for rows read
from the Smartshop CSV files and for equivalent API payloads. CSV adapters are
responsible for converting raw text into values such as ``Decimal``, ``int``,
and ``date`` before calling Pydantic validation; persistence and API routing
remain outside this module.
"""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ProductId = Annotated[
	str,
	Field(pattern=r"^[A-Z]{2,3}[0-9]{4}$", min_length=6, max_length=7),
]
"""Product identifier format used by the CSV files, such as ``SP0001`` or ``SPK0441``."""


Rating = Annotated[float, Field(ge=0, le=5)]
"""Inclusive five-point rating scale used by products and reviews."""


class SmartshopModel(BaseModel):
	"""Common strict configuration shared by all Smartshop models."""

	model_config = ConfigDict(
		extra="forbid",
		str_strip_whitespace=True,
	)


class Product(SmartshopModel):
	"""A catalog product loaded from ``data/products.csv``."""

	id: ProductId
	name: str = Field(min_length=1, max_length=200)
	brand: str = Field(min_length=1, max_length=100)
	category: str = Field(pattern=r"^[a-z][a-z0-9_]*$", min_length=1, max_length=100)
	price: Decimal = Field(gt=0)
	description: str = Field(min_length=1, max_length=1000)
	stock: int = Field(ge=0)
	rating: Rating


class Review(SmartshopModel):
	"""A dated customer review linked to a product identifier."""

	product_id: ProductId
	rating: Rating
	text: str = Field(min_length=1, max_length=2000)
	date: date


class StorePolicy(SmartshopModel):
	"""A store policy from ``data/store_policies.csv``.

	The source CSV stores multiple conditions in one pipe-delimited string.
	Ingestion code should split that value into ``conditions`` before calling
	this model so the application works with a structured list.
	"""

	policy_type: Literal[
		"exchanges",
		"financing",
		"preorder",
		"price_matching",
		"repairs",
		"returns",
		"shipping",
		"warranty",
	]
	description: str = Field(min_length=1, max_length=300)
	conditions: list[str] = Field(min_length=1)
	timeframe: int = Field(ge=0)

	@field_validator("conditions")
	@classmethod
	def validate_conditions(cls, conditions: list[str]) -> list[str]:
		"""Reject blank conditions while normalizing CSV-derived strings."""

		normalized_conditions = [condition.strip() for condition in conditions]
		if any(not condition for condition in normalized_conditions):
			raise ValueError("conditions must contain only non-empty strings")
		return normalized_conditions