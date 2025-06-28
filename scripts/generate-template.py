# scripts/generate-template.py
import yaml
import json
import os
from pathlib import Path

def load_component(component_name, version):
    """コンポーネントファイルを読み込む"""
    component_path = Path(f"components/{component_name}/{version}.yml")
    if not component_path.exists():
        raise FileNotFoundError(f"Component file not found: {component_path}")
    
    with open(component_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def load_recipe(recipe_file):
    """レシピファイルを読み込む"""
    recipe_path = Path(f"recipes/{recipe_file}")
    if not recipe_path.exists():
        raise FileNotFoundError(f"Recipe file not found: {recipe_path}")
    
    with open(recipe_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def generate_cloudformation_template():
    """CloudFormationテンプレートを生成する"""
    
    # レシピを読み込み
    recipe = load_recipe("ubuntu-development.yml")
    
    template = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "AWS Image Builder with external components and recipes",
        "Parameters": {
            "VpcId": {
                "Type": "AWS::EC2::VPC::Id",
                "Description": "VPC ID for Image Builder"
            },
            "SubnetId": {
                "Type": "AWS::EC2::Subnet::Id",
                "Description": "Subnet ID for Image Builder"
            },
            "InstanceProfileArn": {
                "Type": "String",
                "Description": "Instance profile ARN for Image Builder"
            }
        },
        "Resources": {}
    }
    
    # コンポーネントリソースを生成
    components = {}
    for component_ref in recipe.get("components", []):
        component_name = component_ref["name"]
        component_version = component_ref["version"]
        
        # コンポーネントファイルを読み込み
        component_data = load_component(
            component_name.lower().replace(" ", "-"), 
            component_version
        )
        
        # CloudFormationリソース名を生成
        resource_name = f"Component{component_name.replace(' ', '')}"
        
        # コンポーネントリソースを追加
        template["Resources"][resource_name] = {
            "Type": "AWS::ImageBuilder::Component",
            "Properties": {
                "Name": component_data["name"],
                "Description": component_data["description"],
                "Platform": "Linux",
                "Version": component_version,
                "Data": yaml.dump(component_data, default_flow_style=False)
            }
        }
        
        components[component_name] = {
            "ComponentArn": {"Ref": resource_name}
        }
    
    # レシピリソースを生成
    recipe_components = []
    for component_ref in recipe.get("components", []):
        component_name = component_ref["name"]
        resource_name = f"Component{component_name.replace(' ', '')}"
        
        recipe_component = {
            "ComponentArn": {"Ref": resource_name}
        }
        
        if component_ref.get("parameters"):
            recipe_component["Parameters"] = component_ref["parameters"]
        
        recipe_components.append(recipe_component)
    
    template["Resources"]["ImageRecipe"] = {
        "Type": "AWS::ImageBuilder::ImageRecipe",
        "Properties": {
            "Name": recipe["name"],
            "Description": recipe["description"],
            "Version": recipe["version"],
            "ParentImage": recipe["parentImage"],
            "Components": recipe_components
        }
    }
    
    # インフラストラクチャ設定
    template["Resources"]["InfrastructureConfiguration"] = {
        "Type": "AWS::ImageBuilder::InfrastructureConfiguration",
        "Properties": {
            "Name": f"{recipe['name']}Infrastructure",
            "Description": f"Infrastructure configuration for {recipe['name']}",
            "InstanceProfileName": {"Ref": "InstanceProfileArn"},
            "SubnetId": {"Ref": "SubnetId"},
            "SecurityGroupIds": [{"Ref": "ImageBuilderSecurityGroup"}],
            "InstanceTypes": ["t3.medium"],
            "TerminateInstanceOnFailure": True
        }
    }
    
    # セキュリティグループ
    template["Resources"]["ImageBuilderSecurityGroup"] = {
        "Type": "AWS::EC2::SecurityGroup",
        "Properties": {
            "GroupDescription": "Security group for Image Builder",
            "VpcId": {"Ref": "VpcId"},
            "SecurityGroupEgress": [{
                "IpProtocol": "-1",
                "CidrIp": "0.0.0.0/0"
            }]
        }
    }
    
    # 配布設定
    template["Resources"]["DistributionConfiguration"] = {
        "Type": "AWS::ImageBuilder::DistributionConfiguration",
        "Properties": {
            "Name": f"{recipe['name']}Distribution",
            "Description": f"Distribution configuration for {recipe['name']}",
            "Distributions": [{
                "Region": "ap-northeast-1",
                "AmiDistributionConfiguration": {
                    "Name": f"{recipe['name']}-{{{{ imagebuilder:buildDate }}}}",
                    "Description": f"AMI created by {recipe['name']}"
                }
            }]
        }
    }
    
    # イメージパイプライン
    template["Resources"]["ImagePipeline"] = {
        "Type": "AWS::ImageBuilder::ImagePipeline",
        "Properties": {
            "Name": f"{recipe['name']}Pipeline",
            "Description": f"Image pipeline for {recipe['name']}",
            "ImageRecipeArn": {"Ref": "ImageRecipe"},
            "InfrastructureConfigurationArn": {"Ref": "InfrastructureConfiguration"},
            "DistributionConfigurationArn": {"Ref": "DistributionConfiguration"},
            "Status": "ENABLED"
        }
    }
    
    # アウトプット
    template["Outputs"] = {
        "ImageRecipeArn": {
            "Description": "ARN of the Image Recipe",
            "Value": {"Ref": "ImageRecipe"}
        },
        "ImagePipelineArn": {
            "Description": "ARN of the Image Pipeline",
            "Value": {"Ref": "ImagePipeline"}
        },
        "InfrastructureConfigurationArn": {
            "Description": "ARN of the Infrastructure Configuration",
            "Value": {"Ref": "InfrastructureConfiguration"}
        }
    }
    
    return template

def main():
    try:
        template = generate_cloudformation_template()
        
        # テンプレートをファイルに出力
        with open("generated-template.yml", "w", encoding="utf-8") as f:
            yaml.dump(template, f, default_flow_style=False, allow_unicode=True)
        
        print("CloudFormation template generated successfully: generated-template.yml")
        
    except Exception as e:
        print(f"Error generating template: {e}")
        exit(1)

if __name__ == "__main__":
    main()
