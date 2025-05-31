# API Design Document: BOPIS/POS System

## 1. Introduction/Overview

This document outlines the API for a Buy Online, Pick up In Store (BOPIS) and Point of Sale (POS) system. The system is designed to be multi-tenant, allowing different vendors or events to manage their sales and pickup operations independently.

Key features include:
- User management (customers, staff, tenant admins, super admin)
- Multi-tenant product catalog and inventory management
- BOPIS order placement, processing, and pickup verification (QR code based)
- Simplified POS for in-person sales
- Staff assignment and lane management for pickup counters
- Real-time notifications

## 2. Authentication

Authentication is handled using JSON Web Tokens (JWT).

- **Login:** Users authenticate with username and password to receive a JWT access token and a refresh token.
- **Access Token:** The access token is short-lived and must be included in the `Authorization` header for protected endpoints (e.g., `Authorization: Bearer <access_token>`).
- **Refresh Token:** The refresh token is long-lived and can be used to obtain a new access token when the current one expires.
- **Role Handling:** The JWT payload includes the user's role (e.g., `customer`, `picker`, `counter`, `tenant_admin`, `super_admin`) and `tenant_id` (if applicable). API endpoints restrict access based on these roles.

### Pydantic Models for Authentication

```python
from pydantic import BaseModel, EmailStr
from typing import Optional
import datetime

class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str

class TokenPayload(BaseModel):
    sub: Optional[int] = None # User ID
    role: Optional[str] = None
    tenant_id: Optional[int] = None
    exp: Optional[datetime.datetime] = None

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str # Should match UserRole enum values
    tenant_id: Optional[int] = None # Required for non-super_admin roles during creation by admin

class UserLogin(BaseModel):
    username: str # Or email
    password: str
```

## 3. Data Models (SQLAlchemy)

The following are the SQLAlchemy models defining the database structure. These models are located in `BOPIS_Lou/models.py`.

```python
import enum
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Numeric, ForeignKey, Text, Enum as SAEnum, Time, UniqueConstraint
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

# --- Enums ---
class UserRole(enum.Enum):
    customer = "customer"
    picker = "picker"
    counter = "counter"
    tenant_admin = "tenant_admin"
    super_admin = "super_admin"

class OrderType(enum.Enum): # From existing TSD
    BOPIS = "BOPIS"
    POS_SALE = "POS_SALE"

class OrderStatus(enum.Enum): # From existing TSD
    CART = "CART"
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    ORDER_CONFIRMED = "ORDER_CONFIRMED"
    PROCESSING = "PROCESSING"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"

class PaymentStatus(enum.Enum): # From existing TSD
    UNPAID = "UNPAID"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"

class LaneStatus(enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    BUSY = "BUSY"

class NotificationStatus(enum.Enum):
    UNREAD = "UNREAD"
    READ = "READ"
    ARCHIVED = "ARCHIVED"

# --- Models ---
class Tenant(Base): # From existing TSD
    __tablename__ = 'tenants'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    users = relationship("User", back_populates="tenant")
    products = relationship("Product", back_populates="tenant")
    orders = relationship("Order", back_populates="tenant")
    pickup_time_slots = relationship("PickupTimeSlot", back_populates="tenant")
    lanes = relationship("Lane", back_populates="tenant")
    staff_assignments = relationship("StaffAssignment", back_populates="tenant")
    notifications = relationship("Notification", back_populates="tenant")


class User(Base): # From existing TSD, updated
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(SAEnum(UserRole), nullable=False) # UserRole enum updated
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)

    tenant = relationship("Tenant", back_populates="users")
    orders = relationship("Order", back_populates="customer")
    staff_assignments = relationship("StaffAssignment", back_populates="user")
    notifications = relationship("Notification", back_populates="user")


class Product(Base): # From existing TSD, updated
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    sku = Column(String, index=True, nullable=False)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    stock_quantity = Column(Integer, default=0, nullable=False)
    image_url = Column(String, nullable=True)
    version = Column(Integer, nullable=False, server_default='1', default=1) # For optimistic locking
    last_synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()) # For offline sync
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint('sku', 'tenant_id', name='_sku_tenant_uc'),)

    tenant = relationship("Tenant", back_populates="products")
    order_items = relationship("OrderItem", back_populates="product")


class Order(Base): # From existing TSD, updated
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    order_type = Column(SAEnum(OrderType), nullable=False, default=OrderType.BOPIS)
    status = Column(SAEnum(OrderStatus), nullable=False, default=OrderStatus.CART)
    payment_status = Column(SAEnum(PaymentStatus), nullable=False, default=PaymentStatus.UNPAID)
    total_amount = Column(Numeric(10, 2), nullable=False)
    pickup_token = Column(String, unique=True, index=True, nullable=True)

    pickup_slot_id = Column(Integer, ForeignKey('pickup_time_slots.id'), nullable=True)
    assigned_lane_id = Column(Integer, ForeignKey('lanes.id'), nullable=True)
    # For identity verification, perhaps store a specific question or a hint.
    # Example: A product_id from the order to ask "How many of X did you buy?"
    identity_verification_product_id = Column(Integer, ForeignKey('products.id'), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    customer = relationship("User", back_populates="orders")
    tenant = relationship("Tenant", back_populates="orders")
    order_items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    pickup_slot = relationship("PickupTimeSlot", back_populates="orders")
    assigned_lane = relationship("Lane", back_populates="orders_assigned", foreign_keys=[assigned_lane_id])
    # identity_verification_product = relationship("Product", foreign_keys=[identity_verification_product_id])
    notifications = relationship("Notification", back_populates="related_order")


class OrderItem(Base): # From existing TSD
    __tablename__ = 'order_items'
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    quantity = Column(Integer, nullable=False)
    price_at_purchase = Column(Numeric(10, 2), nullable=False)

    order = relationship("Order", back_populates="order_items")
    product = relationship("Product", back_populates="order_items")

# --- New Models ---
class PickupTimeSlot(Base):
    __tablename__ = 'pickup_time_slots'
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False) # Date for the slot
    start_time = Column(Time(timezone=True), nullable=False)
    end_time = Column(Time(timezone=True), nullable=False)
    capacity = Column(Integer, nullable=False, default=10)
    current_orders = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    tenant = relationship("Tenant", back_populates="pickup_time_slots")
    orders = relationship("Order", back_populates="pickup_slot")

class Lane(Base):
    __tablename__ = 'lanes'
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    name = Column(String, nullable=False)
    status = Column(SAEnum(LaneStatus), nullable=False, default=LaneStatus.CLOSED)
    current_order_id = Column(Integer, ForeignKey('orders.id'), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    tenant = relationship("Tenant", back_populates="lanes")
    current_order = relationship("Order", foreign_keys=[current_order_id], post_update=True) # post_update for self-referential FK
    staff_assignments = relationship("StaffAssignment", back_populates="lane")
    orders_assigned = relationship("Order", back_populates="assigned_lane", foreign_keys="Order.assigned_lane_id")


class StaffAssignment(Base):
    __tablename__ = 'staff_assignments'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    assigned_role = Column(SAEnum(UserRole), nullable=False) # picker, counter
    lane_id = Column(Integer, ForeignKey('lanes.id'), nullable=True) # If role is counter and assigned to a specific lane
    start_time = Column(DateTime(timezone=True), server_default=func.now())
    end_time = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="staff_assignments")
    tenant = relationship("Tenant", back_populates="staff_assignments")
    lane = relationship("Lane", back_populates="staff_assignments")

class Notification(Base):
    __tablename__ = 'notifications'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False) # User to be notified
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False) # Associated tenant
    message = Column(Text, nullable=False)
    related_order_id = Column(Integer, ForeignKey('orders.id'), nullable=True)
    status = Column(SAEnum(NotificationStatus), nullable=False, default=NotificationStatus.UNREAD)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    read_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="notifications")
    tenant = relationship("Tenant", back_populates="notifications") # Added tenant relationship
    related_order = relationship("Order", back_populates="notifications")
```

## 4. API Endpoints

Common Error Responses for all endpoints:
- **400 Bad Request:** Invalid request payload, parameters, or format.
- **401 Unauthorized:** Missing or invalid authentication token.
- **403 Forbidden:** Authenticated user does not have permission for the action.
- **404 Not Found:** Resource not found.
- **409 Conflict:** Resource conflict (e.g., unique constraint violation, version mismatch).
- **500 Internal Server Error:** Unexpected server error.

### Common Pydantic Models

```python
from pydantic import BaseModel, EmailStr, condecimal
from typing import List, Optional, Any
import datetime
import decimal # For Numeric type

# Re-define enums for Pydantic models
class UserRoleEnum(str, enum.Enum):
    customer = "customer"
    picker = "picker"
    counter = "counter"
    tenant_admin = "tenant_admin"
    super_admin = "super_admin"

class OrderTypeEnum(str, enum.Enum):
    BOPIS = "BOPIS"
    POS_SALE = "POS_SALE"

class OrderStatusEnum(str, enum.Enum):
    CART = "CART"
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    ORDER_CONFIRMED = "ORDER_CONFIRMED"
    PROCESSING = "PROCESSING"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"

class PaymentStatusEnum(str, enum.Enum):
    UNPAID = "UNPAID"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"

class LaneStatusEnum(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    BUSY = "BUSY"

class NotificationStatusEnum(str, enum.Enum):
    UNREAD = "UNREAD"
    READ = "READ"
    ARCHIVED = "ARCHIVED"

class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: UserRoleEnum
    tenant_id: Optional[int] = None
    is_active: bool
    created_at: datetime.datetime

    class Config:
        orm_mode = True

class ProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: decimal.Decimal
    sku: str
    tenant_id: int
    stock_quantity: int
    image_url: Optional[str] = None
    version: int
    last_synced_at: datetime.datetime
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        orm_mode = True

class OrderItemResponse(BaseModel):
    id: int
    order_id: int
    product_id: int
    quantity: int
    price_at_purchase: decimal.Decimal
    product: Optional[ProductResponse] = None # Optionally populated

    class Config:
        orm_mode = True

class OrderResponse(BaseModel):
    id: int
    user_id: int
    tenant_id: int
    order_type: OrderTypeEnum
    status: OrderStatusEnum
    payment_status: PaymentStatusEnum
    total_amount: decimal.Decimal
    pickup_token: Optional[str] = None
    pickup_slot_id: Optional[int] = None
    assigned_lane_id: Optional[int] = None
    identity_verification_product_id: Optional[int] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    customer: Optional[UserResponse] = None # Optionally populated
    order_items: List[OrderItemResponse] = []

    class Config:
        orm_mode = True

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int
```

### Auth Endpoints

#### 1. Register User
- **POST** `/auth/register`
- **Description:** Allows new customers to register. Tenant admins/Super admins might use different endpoints or mechanisms (e.g., `/tenants/{tenant_id}/staff`).
- **Permissions:** Public (for customer registration).
- **Request Body:** `UserCreate`
- **Success Response:** `201 Created`, `UserResponse`
- **Error Responses:** 400, 409 (username/email exists)

#### 2. Login
- **POST** `/auth/login`
- **Description:** Authenticates a user and returns JWT tokens.
- **Permissions:** Public.
- **Request Body:** `UserLogin`
- **Success Response:** `200 OK`, `Token`
- **Error Responses:** 400, 401 (invalid credentials)

#### 3. Refresh Token
- **POST** `/auth/refresh-token`
- **Description:** Issues a new access token using a valid refresh token.
- **Permissions:** Authenticated (requires valid refresh token).
- **Request Body:**
    ```python
    class RefreshTokenRequest(BaseModel):
        refresh_token: str
    ```
- **Success Response:** `200 OK`, `Token` (with new access_token, potentially new refresh_token)
- **Error Responses:** 401 (invalid or expired refresh token)

### User Endpoints

#### 1. Get Current User
- **GET** `/users/me`
- **Description:** Retrieves the profile of the currently authenticated user.
- **Permissions:** Authenticated (any role).
- **Success Response:** `200 OK`, `UserResponse`

#### 2. Update Current User
- **PUT** `/users/me`
- **Description:** Allows the authenticated user to update their own profile information (e.g., username, email, password - password update would require current password).
- **Permissions:** Authenticated (any role).
- **Request Body:**
    ```python
    class UserUpdate(BaseModel):
        username: Optional[str] = None
        email: Optional[EmailStr] = None
        current_password: Optional[str] = None # Required if changing password
        new_password: Optional[str] = None
    ```
- **Success Response:** `200 OK`, `UserResponse`
- **Error Responses:** 400, 401 (for password change if current_password is wrong), 409

### Staff Management Endpoints (Tenant Admin)

Pydantic Models for Staff:
```python
class StaffCreate(UserCreate): # Inherits from UserCreate, role is fixed by endpoint/logic
    # tenant_id will be from path parameter
    assigned_role: UserRoleEnum # picker or counter

class StaffResponse(UserResponse): # UserResponse is suitable
    pass

class StaffAssignmentCreate(BaseModel):
    user_id: int
    assigned_role: UserRoleEnum # picker or counter
    lane_id: Optional[int] = None # if counter and assigned to specific lane
    # start_time, end_time, is_active can have defaults or be set by system

class StaffAssignmentResponse(BaseModel):
    id: int
    user_id: int
    tenant_id: int
    assigned_role: UserRoleEnum
    lane_id: Optional[int] = None
    start_time: datetime.datetime
    end_time: Optional[datetime.datetime] = None
    is_active: bool
    user: UserResponse # Populated
    lane: Optional[Any] # LaneResponse - define later or use Any for now

    class Config:
        orm_mode = True
```

#### 1. List Staff for Tenant
- **GET** `/tenants/{tenant_id}/staff`
- **Description:** Lists all staff members (users with roles picker, counter, tenant_admin) for a specific tenant.
- **Permissions:** `tenant_admin` (for their own tenant), `super_admin`.
- **Path Parameters:** `tenant_id: int`
- **Query Parameters:** `page: int = 1`, `size: int = 20`, `role: Optional[UserRoleEnum] = None`
- **Success Response:** `200 OK`, `PaginatedResponse[StaffResponse]`

#### 2. Create Staff Member for Tenant
- **POST** `/tenants/{tenant_id}/staff`
- **Description:** Creates a new staff member (picker or counter) for the tenant.
- **Permissions:** `tenant_admin` (for their own tenant), `super_admin`.
- **Path Parameters:** `tenant_id: int`
- **Request Body:** `StaffCreate` (username, email, password, assigned_role)
- **Success Response:** `201 Created`, `StaffResponse`

#### 3. Get Staff Member Details
- **GET** `/tenants/{tenant_id}/staff/{user_id}`
- **Description:** Retrieves details of a specific staff member.
- **Permissions:** `tenant_admin` (for their own tenant), `super_admin`.
- **Path Parameters:** `tenant_id: int`, `user_id: int`
- **Success Response:** `200 OK`, `StaffResponse`

#### 4. Update Staff Member
- **PUT** `/tenants/{tenant_id}/staff/{user_id}`
- **Description:** Updates a staff member's details (e.g., is_active, role - if allowed).
- **Permissions:** `tenant_admin` (for their own tenant), `super_admin`.
- **Path Parameters:** `tenant_id: int`, `user_id: int`
- **Request Body:**
    ```python
    class StaffUpdate(BaseModel):
        is_active: Optional[bool] = None
        assigned_role: Optional[UserRoleEnum] = None # e.g. picker to counter
        # Other fields from UserUpdate if applicable
    ```
- **Success Response:** `200 OK`, `StaffResponse`

#### 5. (De)activate Staff Member (Alternative to PUT for simplicity)
- **PATCH** `/tenants/{tenant_id}/staff/{user_id}/activate`
- **Description:** Activates a staff member.
- **Permissions:** `tenant_admin` (for their own tenant), `super_admin`.
- **Success Response:** `200 OK`, `StaffResponse`

- **PATCH** `/tenants/{tenant_id}/staff/{user_id}/deactivate`
- **Description:** Deactivates a staff member.
- **Permissions:** `tenant_admin` (for their own tenant), `super_admin`.
- **Success Response:** `200 OK`, `StaffResponse`


### Tenant Endpoints (Super Admin)

Pydantic Models for Tenant:
```python
class TenantCreate(BaseModel):
    name: str

class TenantResponse(BaseModel):
    id: int
    name: str
    created_at: datetime.datetime
    # users: List[UserResponse] = [] # Potentially large, consider separate endpoints
    # products: List[ProductResponse] = []

    class Config:
        orm_mode = True
```

#### 1. List Tenants
- **GET** `/tenants`
- **Description:** Lists all tenants.
- **Permissions:** `super_admin`.
- **Query Parameters:** `page: int = 1`, `size: int = 20`
- **Success Response:** `200 OK`, `PaginatedResponse[TenantResponse]`

#### 2. Create Tenant
- **POST** `/tenants`
- **Description:** Creates a new tenant.
- **Permissions:** `super_admin`.
- **Request Body:** `TenantCreate`
- **Success Response:** `201 Created`, `TenantResponse`

#### 3. Get Tenant Details
- **GET** `/tenants/{tenant_id}`
- **Description:** Retrieves details of a specific tenant.
- **Permissions:** `super_admin`, `tenant_admin` (for their own tenant).
- **Path Parameters:** `tenant_id: int`
- **Success Response:** `200 OK`, `TenantResponse`

#### 4. Update Tenant
- **PUT** `/tenants/{tenant_id}`
- **Description:** Updates a tenant's details.
- **Permissions:** `super_admin`.
- **Path Parameters:** `tenant_id: int`
- **Request Body:** `TenantCreate` (e.g. to update name)
- **Success Response:** `200 OK`, `TenantResponse`

### Product Endpoints

Pydantic Models for Product:
```python
class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: decimal.Decimal
    sku: str
    stock_quantity: int = 0
    image_url: Optional[str] = None
    # tenant_id is implicit from authenticated tenant_admin

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[decimal.Decimal] = None
    stock_quantity: Optional[int] = None
    image_url: Optional[str] = None
    # version is handled by server for optimistic locking
```

#### 1. List Products for Tenant
- **GET** `/products` (Implicitly scoped to tenant via auth) or `/tenants/{tenant_id}/products` (Explicit)
- **Description:** Lists all products for the authenticated tenant admin or a specified tenant (for super_admin). Customers would use a public version, possibly `/public/tenants/{tenant_id}/products`.
- **Permissions:** `tenant_admin`, `super_admin`. (Public version for customers)
- **Query Parameters:** `page: int = 1`, `size: int = 20`, `updated_since: Optional[datetime.datetime] = None` (for delta sync), `sku: Optional[str] = None`
- **Success Response:** `200 OK`, `PaginatedResponse[ProductResponse]`

#### 2. Create Product
- **POST** `/products`
- **Description:** Creates a new product for the tenant. `tenant_id` taken from authenticated `tenant_admin`.
- **Permissions:** `tenant_admin`.
- **Request Body:** `ProductCreate`
- **Success Response:** `201 Created`, `ProductResponse`

#### 3. Get Product Details
- **GET** `/products/{product_id}`
- **Description:** Retrieves details of a specific product. Scoped by tenant.
- **Permissions:** `tenant_admin`, `super_admin`. (Public for customers)
- **Path Parameters:** `product_id: int`
- **Success Response:** `200 OK`, `ProductResponse`

#### 4. Update Product
- **PUT** `/products/{product_id}`
- **Description:** Updates a product's details. Uses `version` for optimistic locking.
- **Permissions:** `tenant_admin`.
- **Path Parameters:** `product_id: int`
- **Request Body:** `ProductUpdate` (include `version` if optimistic locking is client-enforced, or server handles it via ETag/If-Match header)
    ```python
    class ProductUpdateWithVersion(ProductUpdate):
        version: int # Required for optimistic lock check
    ```
- **Success Response:** `200 OK`, `ProductResponse`
- **Error Responses:** 409 (version mismatch)

#### 5. Delete Product
- **DELETE** `/products/{product_id}`
- **Description:** Deletes a product. (Consider soft delete)
- **Permissions:** `tenant_admin`.
- **Path Parameters:** `product_id: int`
- **Success Response:** `204 No Content`

### Pickup Time Slot Endpoints (Tenant Admin)

Pydantic Models for PickupTimeSlot:
```python
class PickupTimeSlotBase(BaseModel):
    date: datetime.date # Keep as date for API, convert to datetime internally if needed
    start_time: datetime.time
    end_time: datetime.time
    capacity: int
    is_active: bool = True

class PickupTimeSlotCreate(PickupTimeSlotBase):
    pass # tenant_id from path

class PickupTimeSlotResponse(PickupTimeSlotBase):
    id: int
    tenant_id: int
    current_orders: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        orm_mode = True
```

#### 1. List Pickup Time Slots for Tenant
- **GET** `/tenants/{tenant_id}/pickup-slots`
- **Description:** Lists all pickup time slots for a tenant.
- **Permissions:** `tenant_admin`, `customer` (for available slots).
- **Path Parameters:** `tenant_id: int`
- **Query Parameters:** `page: int = 1`, `size: int = 20`, `date_from: Optional[datetime.date] = None`, `date_to: Optional[datetime.date] = None`, `is_active: Optional[bool] = True`
- **Success Response:** `200 OK`, `PaginatedResponse[PickupTimeSlotResponse]`

#### 2. Create Pickup Time Slot
- **POST** `/tenants/{tenant_id}/pickup-slots`
- **Description:** Creates a new pickup time slot for the tenant.
- **Permissions:** `tenant_admin`.
- **Path Parameters:** `tenant_id: int`
- **Request Body:** `PickupTimeSlotCreate`
- **Success Response:** `201 Created`, `PickupTimeSlotResponse`

#### 3. Get Pickup Time Slot Details
- **GET** `/tenants/{tenant_id}/pickup-slots/{slot_id}`
- **Description:** Retrieves details of a specific pickup time slot.
- **Permissions:** `tenant_admin`.
- **Path Parameters:** `tenant_id: int`, `slot_id: int`
- **Success Response:** `200 OK`, `PickupTimeSlotResponse`

#### 4. Update Pickup Time Slot
- **PUT** `/tenants/{tenant_id}/pickup-slots/{slot_id}`
- **Description:** Updates a pickup time slot's details.
- **Permissions:** `tenant_admin`.
- **Path Parameters:** `tenant_id: int`, `slot_id: int`
- **Request Body:** `PickupTimeSlotCreate` (or a `PickupTimeSlotUpdate` model with all fields optional)
- **Success Response:** `200 OK`, `PickupTimeSlotResponse`

#### 5. Delete Pickup Time Slot
- **DELETE** `/tenants/{tenant_id}/pickup-slots/{slot_id}`
- **Description:** Deletes a pickup time slot (consider implications if orders are assigned).
- **Permissions:** `tenant_admin`.
- **Path Parameters:** `tenant_id: int`, `slot_id: int`
- **Success Response:** `204 No Content`


### Lane Endpoints (Tenant Admin)

Pydantic Models for Lane:
```python
class LaneBase(BaseModel):
    name: str
    status: LaneStatusEnum = LaneStatusEnum.CLOSED

class LaneCreate(LaneBase):
    pass # tenant_id from path

class LaneResponse(LaneBase):
    id: int
    tenant_id: int
    current_order_id: Optional[int] = None
    # current_order: Optional[OrderResponse] = None # Populate if needed
    # staff_assignments: List[StaffAssignmentResponse] = [] # Populate if needed
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        orm_mode = True

class LaneStatusUpdate(BaseModel):
    status: LaneStatusEnum
```

#### 1. List Lanes for Tenant
- **GET** `/tenants/{tenant_id}/lanes`
- **Description:** Lists all lanes for a tenant.
- **Permissions:** `tenant_admin`, `counter` staff.
- **Path Parameters:** `tenant_id: int`
- **Query Parameters:** `page: int = 1`, `size: int = 20`, `status: Optional[LaneStatusEnum] = None`
- **Success Response:** `200 OK`, `PaginatedResponse[LaneResponse]`

#### 2. Create Lane
- **POST** `/tenants/{tenant_id}/lanes`
- **Description:** Creates a new lane for the tenant.
- **Permissions:** `tenant_admin`.
- **Path Parameters:** `tenant_id: int`
- **Request Body:** `LaneCreate`
- **Success Response:** `201 Created`, `LaneResponse`

#### 3. Get Lane Details
- **GET** `/tenants/{tenant_id}/lanes/{lane_id}`
- **Description:** Retrieves details of a specific lane.
- **Permissions:** `tenant_admin`, `counter` staff.
- **Path Parameters:** `tenant_id: int`, `lane_id: int`
- **Success Response:** `200 OK`, `LaneResponse`

#### 4. Update Lane
- **PUT** `/tenants/{tenant_id}/lanes/{lane_id}`
- **Description:** Updates a lane's details (e.g., name). Status updated via separate endpoint.
- **Permissions:** `tenant_admin`.
- **Path Parameters:** `tenant_id: int`, `lane_id: int`
- **Request Body:** `LaneCreate` (or a `LaneUpdate` model)
- **Success Response:** `200 OK`, `LaneResponse`

#### 5. Update Lane Status
- **PATCH** `/tenants/{tenant_id}/lanes/{lane_id}/status`
- **Description:** Updates the status of a lane (OPEN, CLOSED, BUSY).
- **Permissions:** `tenant_admin`, `counter` staff.
- **Path Parameters:** `tenant_id: int`, `lane_id: int`
- **Request Body:** `LaneStatusUpdate`
- **Success Response:** `200 OK`, `LaneResponse`

#### 6. Assign Staff to Lane (Covered by StaffAssignment model, could be part of Staff or Lane resource)
- **POST** `/tenants/{tenant_id}/lanes/{lane_id}/assign-staff`
- **Description:** Assigns a staff member (counter) to a lane. (This might be better handled through the StaffAssignment resource itself).
- **Permissions:** `tenant_admin`.
- **Path Parameters:** `tenant_id: int`, `lane_id: int`
- **Request Body:**
    ```python
    class LaneStaffAssignmentRequest(BaseModel):
        user_id: int # Staff user_id
        # assigned_role should be 'counter'
    ```
- **Success Response:** `200 OK`, `StaffAssignmentResponse` (or `LaneResponse` with updated assignments)

### Picker Workflow Endpoints

Pydantic Models for Picker Workflow:
```python
class OrderItemPickerUpdate(BaseModel):
    product_id: int
    quantity_picked: int # Could be different from ordered if partial picking allowed
    # is_substituted: Optional[bool] = False # Future
    # substitution_product_id: Optional[int] = None # Future

class OrderPickingUpdateRequest(BaseModel):
    items: List[OrderItemPickerUpdate]
    notes: Optional[str] = None

class OrderSummaryPicker(OrderResponse): # Inherit and add/modify fields if needed
    # Could add specific picker notes or urgency flags
    pass
```

#### 1. List Orders for Picking
- **GET** `/picker/orders`
- **Description:** Retrieves orders assigned to the picker or generally available for picking (status `ORDER_CONFIRMED` or `PROCESSING`). Tenant is implicit from picker's profile.
- **Permissions:** `picker`.
- **Query Parameters:** `page: int = 1`, `size: int = 20`, `status: OrderStatusEnum = OrderStatusEnum.ORDER_CONFIRMED` (can also query `PROCESSING`)
- **Success Response:** `200 OK`, `PaginatedResponse[OrderSummaryPicker]`

#### 2. Get Order Details for Picking
- **GET** `/picker/orders/{order_id}`
- **Description:** Retrieves full details of an order for picking.
- **Permissions:** `picker`.
- **Path Parameters:** `order_id: int`
- **Success Response:** `200 OK`, `OrderSummaryPicker` (with full order_items and product details)

#### 3. Start Picking Order
- **POST** `/picker/orders/{order_id}/start-picking`
- **Description:** Marks an order as `PROCESSING`. Assigns the order to the picker if not already.
- **Permissions:** `picker`.
- **Path Parameters:** `order_id: int`
- **Success Response:** `200 OK`, `OrderSummaryPicker` (updated status)

#### 4. Update Picking Progress / Mark Items as Picked
- **PUT** `/picker/orders/{order_id}/update-picking`
- **Description:** Picker updates the status of picked items (e.g., quantity found, substitutions). This is more for detailed tracking if needed. Simpler flow might skip this.
- **Permissions:** `picker`.
- **Path Parameters:** `order_id: int`
- **Request Body:** `OrderPickingUpdateRequest`
- **Success Response:** `200 OK`, `OrderSummaryPicker`

#### 5. Mark Order as Ready for Pickup
- **POST** `/picker/orders/{order_id}/ready-for-pickup`
- **Description:** Marks an order as `READY_FOR_PICKUP`.
- **Permissions:** `picker`.
- **Path Parameters:** `order_id: int`
- **Request Body:** (Optional) Notes from picker.
    ```python
    class ReadyForPickupRequest(BaseModel):
        notes: Optional[str] = None
    ```
- **Success Response:** `200 OK`, `OrderSummaryPicker` (updated status)

### Counter Workflow Endpoints

Pydantic Models for Counter Workflow:
```python
class OrderVerificationInfo(BaseModel): # Information to help verify customer
    order_id: int
    customer_username: str
    # Example verification detail:
    identity_verification_product_name: Optional[str] = None
    identity_verification_product_quantity: Optional[int] = None

class AssignToLaneRequest(BaseModel):
    lane_id: int
```

#### 1. List Orders for Counter
- **GET** `/counter/orders`
- **Description:** Retrieves orders that are `READY_FOR_PICKUP` or `PROCESSING` (if counter also handles problem orders). Tenant implicit from counter's profile.
- **Permissions:** `counter`.
- **Query Parameters:** `page: int = 1`, `size: int = 20`, `status: OrderStatusEnum = OrderStatusEnum.READY_FOR_PICKUP`, `pickup_token: Optional[str] = None` (for quick search)
- **Success Response:** `200 OK`, `PaginatedResponse[OrderResponse]`

#### 2. Get Order Details for Counter
- **GET** `/counter/orders/{order_id}`
- **Description:** Retrieves full details of an order for counter staff.
- **Permissions:** `counter`.
- **Path Parameters:** `order_id: int`
- **Success Response:** `200 OK`, `OrderResponse`

#### 3. Assign Order to Lane
- **POST** `/counter/orders/{order_id}/assign-to-lane`
- **Description:** Assigns an order to a specific lane for pickup. Updates lane status to `BUSY` and sets `current_order_id`.
- **Permissions:** `counter`.
- **Path Parameters:** `order_id: int`
- **Request Body:** `AssignToLaneRequest`
- **Success Response:** `200 OK`, `OrderResponse` (with `assigned_lane_id`) and `LaneResponse` (or just confirm with 200 OK and updated order)
- **Error Responses:** 409 (Lane not OPEN or already BUSY with another order)

#### 4. Verify Customer Identity & Retrieve Order (Covered by `/orders/verify-pickup`)
- This step is primarily handled by the `/orders/verify-pickup` endpoint using the `pickup_token`.

#### 5. Mark Order as Completed (Covered by `/orders/{order_id}/complete-pickup`)
- This step is handled after successful verification.

### Order Operations Endpoints

Pydantic Models for Order Operations:
```python
class CartItemCreate(BaseModel):
    product_id: int
    quantity: int

class CartItemUpdate(BaseModel):
    quantity: int # Must be > 0, or use DELETE to remove

class CheckoutRequest(BaseModel):
    pickup_slot_id: int
    # payment_details: Optional[Any] # For actual payment integration, mock for now
    identity_verification_product_id: Optional[int] = None # Customer might pre-select for faster pickup

class OrderPickupTokenVerificationRequest(BaseModel):
    pickup_token: str

class OrderCompletionRequest(BaseModel):
    # Optional details, e.g. staff notes
    notes: Optional[str] = None
```

#### 1. Get Shopping Cart
- **GET** `/orders/cart`
- **Description:** Retrieves the current user's shopping cart (an order with status `CART`). Creates one if none exists.
- **Permissions:** `customer`.
- **Success Response:** `200 OK`, `OrderResponse`

#### 2. Add Item to Cart
- **POST** `/orders/cart/items`
- **Description:** Adds a product item to the shopping cart.
- **Permissions:** `customer`.
- **Request Body:** `CartItemCreate`
- **Success Response:** `200 OK` (or `201 Created` if item is new), `OrderResponse` (updated cart)
- **Error Responses:** 400 (product not available, insufficient stock if checked at this stage)

#### 3. Update Item in Cart
- **PUT** `/orders/cart/items/{item_id}`
- **Description:** Updates the quantity of an item in the cart.
- **Permissions:** `customer`.
- **Path Parameters:** `item_id: int` (OrderItem ID)
- **Request Body:** `CartItemUpdate`
- **Success Response:** `200 OK`, `OrderResponse` (updated cart)

#### 4. Remove Item from Cart
- **DELETE** `/orders/cart/items/{item_id}`
- **Description:** Removes an item from the shopping cart.
- **Permissions:** `customer`.
- **Path Parameters:** `item_id: int` (OrderItem ID)
- **Success Response:** `200 OK`, `OrderResponse` (updated cart)

#### 5. Checkout Cart
- **POST** `/orders/{cart_order_id}/checkout`
- **Description:** Converts a cart order to a placed order (`ORDER_CONFIRMED` or `PENDING_PAYMENT`). Performs inventory checks, assigns pickup slot, generates pickup token.
- **Permissions:** `customer`.
- **Path Parameters:** `cart_order_id: int` (ID of the order with status CART)
- **Request Body:** `CheckoutRequest`
- **Success Response:** `200 OK`, `OrderResponse` (updated order with status, pickup_token)
- **Error Responses:** 400 (insufficient stock, invalid pickup slot, slot capacity full)

#### 6. List Orders
- **GET** `/orders`
- **Description:** Lists orders for the authenticated user. Admins/staff might have broader access based on tenant.
- **Permissions:** `customer` (own orders), `picker`, `counter`, `tenant_admin` (tenant orders), `super_admin` (all orders).
- **Query Parameters:** `page: int = 1`, `size: int = 20`, `status: Optional[OrderStatusEnum] = None`, `order_type: Optional[OrderTypeEnum] = None`
- **Success Response:** `200 OK`, `PaginatedResponse[OrderResponse]`

#### 7. Get Order Details
- **GET** `/orders/{order_id}`
- **Description:** Retrieves details of a specific order.
- **Permissions:** `customer` (own order), `picker`, `counter`, `tenant_admin`, `super_admin`.
- **Path Parameters:** `order_id: int`
- **Success Response:** `200 OK`, `OrderResponse` (with `order_items`, `customer`, `product` details populated as needed)

#### 8. Verify Pickup Token & Get Order Info
- **POST** `/orders/verify-pickup`
- **Description:** Verifies a pickup token (from QR code) and returns order information for verification by counter staff.
- **Permissions:** `counter`.
- **Request Body:** `OrderPickupTokenVerificationRequest`
- **Success Response:** `200 OK`, `OrderVerificationInfo` (includes order ID, customer name, and a product from the order to ask about, e.g., "How many X did you buy?")
- **Error Responses:** 404 (token not found), 400 (order not ready for pickup)

#### 9. Complete BOPIS Pickup
- **POST** `/orders/{order_id}/complete-pickup`
- **Description:** Marks a BOPIS order as `COMPLETED` after successful verification. Updates lane status if applicable.
- **Permissions:** `counter`.
- **Path Parameters:** `order_id: int`
- **Request Body:** `OrderCompletionRequest` (optional notes)
- **Success Response:** `200 OK`, `OrderResponse` (updated status)

### POS Endpoints

Pydantic Models for POS:
```python
class POSOrderItem(BaseModel):
    product_id: int
    quantity: int

class POSOrderCreate(BaseModel):
    items: List[POSOrderItem]
    # payment_method: str # e.g., "cash", "card" - for record keeping
    # staff_id is implicit from authenticated counter/staff
    # tenant_id is implicit
    idempotency_key: Optional[str] = None # For client-side idempotency

# POSOrderResponse can use the standard OrderResponse
```

#### 1. Create POS Order
- **POST** `/pos/orders`
- **Description:** Creates a new POS order. Decrements inventory. Order status is immediately `COMPLETED`.
- **Permissions:** `counter`, `tenant_admin` (if they also operate POS).
- **Request Body:** `POSOrderCreate`
- **Header:** `Idempotency-Key: <uuid>` (Optional, for preventing duplicate orders on retries)
- **Success Response:** `201 Created`, `OrderResponse`
- **Error Responses:** 400 (insufficient stock), 409 (idempotency key already processed)

### Notification Endpoints

Pydantic Models for Notification:
```python
class NotificationResponse(BaseModel):
    id: int
    user_id: int
    tenant_id: int
    message: str
    related_order_id: Optional[int] = None
    status: NotificationStatusEnum
    created_at: datetime.datetime
    read_at: Optional[datetime.datetime] = None
    # user: UserResponse # Optional, if needed
    # related_order: OrderResponse # Optional, if needed

    class Config:
        orm_mode = True

class NotificationUpdate(BaseModel):
    status: NotificationStatusEnum # e.g., mark as READ or ARCHIVED
```

#### 1. List Notifications for User
- **GET** `/notifications`
- **Description:** Lists notifications for the authenticated user.
- **Permissions:** Authenticated (any role).
- **Query Parameters:** `page: int = 1`, `size: int = 20`, `status: Optional[NotificationStatusEnum] = NotificationStatusEnum.UNREAD`
- **Success Response:** `200 OK`, `PaginatedResponse[NotificationResponse]`

#### 2. Mark Notification as Read/Archived
- **PATCH** `/notifications/{notification_id}`
- **Description:** Updates the status of a notification (e.g., to READ or ARCHIVED).
- **Permissions:** Authenticated (owner of the notification).
- **Path Parameters:** `notification_id: int`
- **Request Body:** `NotificationUpdate`
- **Success Response:** `200 OK`, `NotificationResponse`

## 5. Cross-Cutting Concerns

### Offline Support & Synchronization
- **Idempotency:** Critical for POS transactions and order updates. Use `Idempotency-Key` header for relevant POST/PUT requests. Server stores and checks these keys to prevent duplicate operations.
- **Delta Synchronization:** For product catalogs, orders, etc., mobile clients should use an `updated_since` timestamp parameter in GET requests to fetch only changed/new records. The `last_synced_at` field in models like `Product` helps track this.
- **Optimistic Locking:** The `version` field in models like `Product` helps prevent lost updates when multiple users/systems might modify the same resource. The client sends the known `version`, and the server rejects the update if the current version is different (HTTP 409 Conflict).

### Error Handling
- Consistent JSON error responses with appropriate HTTP status codes.
- Example error response body:
  ```json
  {
    "detail": "Error message or description of issues.",
    "errors": [ // Optional: for validation errors
      {"loc": ["body", "field_name"], "msg": "Specific error for this field", "type": "validation_error_type"}
    ]
  }
  ```

### Pagination
- List endpoints will use cursor-based or offset-based pagination.
- Query Parameters: `page: int` (or `cursor: str`), `size: int`.
- Response Body: Include pagination details (total items, total pages, current page, next/prev links or cursors).
  ```json
  {
    "items": [...],
    "total": 100,
    "page": 1,
    "size": 20,
    "pages": 5
    // "next_cursor": "...", "prev_cursor": "..." // For cursor-based
  }
  ```
  The `PaginatedResponse[T]` Pydantic model reflects this.

This Markdown document provides a comprehensive overview of the API design.
