from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from .models import Industry, Category
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username = serializers.CharField(required=False)

    def validate(self, attrs):
        # Support both 'username' and 'email' keys
        username = attrs.get('username') or attrs.get('email')
        password = attrs.get('password')

        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                # If username login fails, try finding user by email
                try:
                    user_obj = User.objects.get(email=username)
                    user = authenticate(username=user_obj.username, password=password)
                except User.DoesNotExist:
                    pass

            if user:
                if not user.is_active:
                    raise serializers.ValidationError('User account is disabled.')
                
                # Proceed with standard token generation
                data = super().validate({'username': user.username, 'password': password})
                return data

        raise serializers.ValidationError('No active account found with the given credentials')


class IndustrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Industry
        fields = ['id', 'name', 'code']


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'code']


class UserProfileSerializer(serializers.ModelSerializer):
    industry = IndustrySerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    industry_id = serializers.PrimaryKeyRelatedField(
        queryset=Industry.objects.all(), source='industry', write_only=True, required=False, allow_null=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category', write_only=True, required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'phone', 'organization', 'position',
            'industry', 'industry_id',
            'category', 'category_id',
            'profile_picture', 'is_onboarded',
            'date_joined',
        ]
        read_only_fields = ['id', 'role', 'date_joined']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True)
    industry_id = serializers.PrimaryKeyRelatedField(
        queryset=Industry.objects.all(), source='industry', required=False, allow_null=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category', required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password2',
            'first_name', 'last_name',
            'phone', 'organization', 'position',
            'industry_id', 'category_id',
        ]

    def validate(self, data):
        if data['password'] != data.pop('password2'):
            raise serializers.ValidationError({'password2': 'Passwords do not match.'})
        return data

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class AdminUserSerializer(serializers.ModelSerializer):
    """For admin managing users."""
    industry = IndustrySerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    industry_id = serializers.PrimaryKeyRelatedField(
        queryset=Industry.objects.all(), source='industry', write_only=True, required=False, allow_null=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category', write_only=True, required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'is_active', 'phone', 'organization', 'position',
            'industry', 'industry_id',
            'category', 'category_id',
            'date_joined',
        ]
        read_only_fields = ['id', 'date_joined']
