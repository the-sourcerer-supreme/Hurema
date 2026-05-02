from sqlalchemy.ext.asyncio import AsyncSession
from app.crud.leave import LeaveCRUD
from app.schemas.leave import LeaveRequestCreate


class LeaveService:
    @staticmethod
    async def request_leave(session: AsyncSession, user_id: int, leave_request: LeaveRequestCreate):
        return await LeaveCRUD.create_leave_request(session, user_id, leave_request)

    @staticmethod
    async def list_leave_requests(session: AsyncSession, user_id: int):
        return await LeaveCRUD.list_leave_requests_for_user(session, user_id)

    @staticmethod
    async def approve_leave_request(session: AsyncSession, request_id: int, approver_id: int):
        leave_request = await LeaveCRUD.get_leave_request(session, request_id)
        if not leave_request:
            raise ValueError("Leave request not found")
        leave_request.status = "Approved"
        leave_request.approved_by = approver_id
        await LeaveCRUD.update_leave_request(session, leave_request)
        return {
            "message": "Leave request approved",
            "request_id": leave_request.id,
            "status": leave_request.status,
        }
