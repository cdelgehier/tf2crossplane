import pytest

# These fixtures simulate the output of parse_variables() and parse_outputs()
# for several terraform-aws-* modules. They cover a range of Terraform types
# (scalar, collection, optional, nested object) so that test_xrd.py and
# test_composition.py can validate the full parser/generator pipeline without
# cloning any real Git repo.


# ── terraform-aws-s3-bucket ──────────────────────────────────────────────────


@pytest.fixture
def s3_variables() -> dict:
    return {
        "bucket": {"type": "string", "description": "Bucket name", "default": None},
        "force_destroy": {
            "type": "bool",
            "description": "Force destroy",
            "default": False,
        },
        "tags": {"type": "map(string)", "description": "Tags", "default": {}},
        "versioning": {
            "type": "object({enabled = bool})",
            "description": "Versioning config",
            "default": None,
        },
        "allowed_cidrs": {
            "type": "list(string)",
            "description": "Allowed CIDRs",
            "default": [],
        },
    }


@pytest.fixture
def s3_outputs() -> dict:
    return {
        "s3_bucket_id": {"description": "Bucket ID"},
        "s3_bucket_arn": {"description": "Bucket ARN"},
    }


# ── terraform-aws-ec2-instance ───────────────────────────────────────────────


@pytest.fixture
def ec2_variables() -> dict:
    return {
        "name": {"type": "string", "description": "Instance name", "default": None},
        "ami": {"type": "string", "description": "AMI ID", "default": None},
        "instance_type": {
            "type": "string",
            "description": "Instance type",
            "default": "t3.micro",
        },
        "instance_count": {
            "type": "number",
            "description": "Number of instances",
            "default": 1,
        },
        "monitoring": {
            "type": "bool",
            "description": "Enable detailed monitoring",
            "default": False,
        },
        "vpc_security_group_ids": {
            "type": "list(string)",
            "description": "Security group IDs",
            "default": [],
        },
        "tags": {"type": "map(string)", "description": "Tags", "default": {}},
    }


@pytest.fixture
def ec2_outputs() -> dict:
    return {
        "instance_id": {"description": "Instance ID"},
        "instance_arn": {"description": "Instance ARN"},
        "public_ip": {"description": "Public IP address"},
    }


# ── terraform-aws-autoscaling ────────────────────────────────────────────────
# Exercises optional() and deeply nested object types (mixed_instances_policy).


@pytest.fixture
def asg_variables() -> dict:
    return {
        "name": {"type": "string", "description": "ASG name", "default": None},
        "min_size": {"type": "number", "description": "Min size", "default": 0},
        "max_size": {"type": "number", "description": "Max size", "default": None},
        # optional scalar with a default value
        "desired_capacity": {
            "type": "optional(number, null)",
            "description": "Desired capacity",
            "default": None,
        },
        # deeply nested: object({field = optional(object({...}))})
        "mixed_instances_policy": {
            "type": (
                "object({"
                "instances_distribution = optional(object({"
                "on_demand_allocation_strategy = optional(string), "
                "on_demand_base_capacity = optional(number), "
                "spot_allocation_strategy = optional(string)"
                "})), "
                "launch_template = object({"
                "launch_template_specification = optional(object({"
                "launch_template_id = optional(string), "
                "version = optional(string)"
                "}))"
                "})"
                "})"
            ),
            "description": "Mixed instances policy",
            "default": None,
        },
        "tags": {"type": "map(string)", "description": "Tags", "default": {}},
    }


@pytest.fixture
def asg_outputs() -> dict:
    return {
        "autoscaling_group_id": {"description": "ASG ID"},
        "autoscaling_group_name": {"description": "ASG name"},
        "autoscaling_group_arn": {"description": "ASG ARN"},
    }


# ── terraform-aws-alb ────────────────────────────────────────────────────────
# Exercises: required scalars (name, vpc_id), list(string) for subnets and
# security_groups, any-typed complex vars (listeners, target_groups) that map
# to object+preserve-unknown-fields, and map(string) for access_logs.


@pytest.fixture
def alb_variables() -> dict:
    return {
        "name": {"type": "string", "description": "LB name", "default": None},
        "vpc_id": {"type": "string", "description": "VPC ID", "default": None},
        "subnets": {
            "type": "list(string)",
            "description": "Subnet IDs",
            "default": None,
        },
        "internal": {"type": "bool", "description": "Internal LB", "default": False},
        "load_balancer_type": {
            "type": "string",
            "description": "LB type",
            "default": "application",
        },
        "security_groups": {
            "type": "list(string)",
            "description": "Security group IDs",
            "default": [],
        },
        "access_logs": {
            "type": "map(string)",
            "description": "Access logging config",
            "default": {},
        },
        # any-typed → object + x-kubernetes-preserve-unknown-fields
        "listeners": {
            "type": "${any}",
            "description": "Listener configurations",
            "default": {},
        },
        "target_groups": {
            "type": "${any}",
            "description": "Target group configurations",
            "default": {},
        },
        "tags": {"type": "map(string)", "description": "Tags", "default": {}},
    }


@pytest.fixture
def alb_outputs() -> dict:
    return {
        "arn": {"description": "LB ARN"},
        "dns_name": {"description": "LB DNS name"},
        "zone_id": {"description": "Canonical hosted zone ID"},
    }
