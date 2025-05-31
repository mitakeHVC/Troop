import enum
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Numeric, ForeignKey, Text, Enum as SAEnum, Time, UniqueConstraint # Keep other sqlalchemy imports
from sqlalchemy.orm import relationship # Keep other sqlalchemy imports
from sqlalchemy.sql import func

from app.db.base import Base # Changed: Import Base from app.db.base

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
