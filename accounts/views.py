import random
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from .models import Industry, Category, PasswordResetOTP
from .serializers import (
    RegisterSerializer, UserProfileSerializer,
    IndustrySerializer, CategorySerializer, AdminUserSerializer,
    CustomTokenObtainPairSerializer, ChangePasswordSerializer,
    ResetPasswordRequestSerializer, ResetPasswordConfirmSerializer
)
from .permissions import IsSuperAdmin, IsAdminOrAbove


User = get_user_model()


from rest_framework_simplejwt.views import TokenObtainPairView


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserProfileSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            if not user.check_password(serializer.data.get('old_password')):
                return Response({'old_password': ['Wrong password.']}, status=status.HTTP_400_BAD_REQUEST)
            
            user.set_password(serializer.data.get('new_password'))
            user.save()
            return Response({'detail': 'Password updated successfully.'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class IndustryListView(generics.ListAPIView):
    serializer_class = IndustrySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = Industry.objects.filter(is_active=True)
        category_id = self.request.query_params.get('category_id')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        return queryset


class CategoryListView(generics.ListAPIView):
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
    queryset = Category.objects.filter(is_active=True)


class UserListView(generics.ListCreateAPIView):
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminOrAbove]

    def get_queryset(self):
        qs = User.objects.all().order_by('-date_joined')
        role = self.request.query_params.get('role')
        if role:
            qs = qs.filter(role=role)
        return qs


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminOrAbove]
    queryset = User.objects.all()


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request):
    """
    Revokes the user's tokens on logout:
    1. Updates user.last_logout timestamp (revoking all access tokens issued prior to logout).
    2. Blacklists the refresh token if provided.
    """
    user = request.user
    if user and user.is_authenticated:
        user.last_logout = timezone.now()
        user.save(update_fields=['last_logout'])

    try:
        refresh_token = request.data.get('refresh')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        return Response({'detail': 'Logged out successfully.'})
    except Exception:
        return Response({'detail': 'Logged out successfully.'})


class RequestPasswordResetView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResetPasswordRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email=email)
            # Generate a 6-digit OTP
            otp = f"{random.randint(100000, 999999)}"
            # Delete old unused OTPs for this user to keep it clean
            PasswordResetOTP.objects.filter(user=user, is_used=False).delete()
            # Save new OTP
            PasswordResetOTP.objects.create(user=user, otp=otp)
            
            # Send Email
            subject = "FFIMS Password Reset Verification Code"
            message = (
                f"Hello {user.username},\n\n"
                f"You requested a password reset for your FFIMS account.\n"
                f"Your 6-digit verification code (OTP) is: {otp}\n\n"
                f"This code will expire in 10 minutes.\n\n"
                f"If you did not request this, please ignore this email."
            )
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL or 'noreply@survio.com',
                [email],
                fail_silently=False,
            )
        except User.DoesNotExist:
            # Silently succeed to prevent user enumeration
            pass
        except Exception as e:
            # Log mail sending or other errors but don't crash
            print(f"Error sending password reset email: {e}")

        return Response(
            {'detail': 'If this email is registered, a password reset code has been sent.'},
            status=status.HTTP_200_OK
        )


class ResetPasswordConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResetPasswordConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        new_password = serializer.validated_data['new_password']

        try:
            user = User.objects.get(email=email)
            # Find the latest unused OTP
            otp_obj = PasswordResetOTP.objects.filter(user=user, is_used=False).first()
            
            if not otp_obj or otp_obj.otp != otp:
                return Response({'otp': ['Invalid verification code.']}, status=status.HTTP_400_BAD_REQUEST)

            # Check expiration (10 minutes)
            if timezone.now() - otp_obj.created_at > timedelta(minutes=10):
                return Response({'otp': ['Verification code has expired.']}, status=status.HTTP_400_BAD_REQUEST)

            # Valid OTP, update password
            user.set_password(new_password)
            user.save()

            # Mark OTP as used
            otp_obj.is_used = True
            otp_obj.save()

            return Response({'detail': 'Password reset successfully.'}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({'email': ['No user found with this email.']}, status=status.HTTP_400_BAD_REQUEST)

