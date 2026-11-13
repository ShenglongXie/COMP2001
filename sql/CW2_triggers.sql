SET NOCOUNT ON;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

IF OBJECT_ID('CW2.MemberAuditLog', 'U') IS NULL
BEGIN
    CREATE TABLE CW2.MemberAuditLog
    (
        AuditId    BIGINT       IDENTITY(1,1) NOT NULL,
        MemberId   BIGINT       NOT NULL,
        Username   NVARCHAR(30) NOT NULL,
        Email      NVARCHAR(320) NULL,
        FirstName  NVARCHAR(60) NULL,
        LastName   NVARCHAR(60) NULL,
        JoinedAt   DATETIME2(0) NOT NULL,
        LoggedAt   DATETIME2(0) NOT NULL CONSTRAINT DF_MemberAuditLog_LoggedAt DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT PK_MemberAuditLog PRIMARY KEY (AuditId)
    );
END;
GO

CREATE OR ALTER TRIGGER CW2.trg_Member_AfterInsert
ON CW2.Member
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO CW2.MemberAuditLog (MemberId, Username, Email, FirstName, LastName, JoinedAt)
    SELECT i.MemberId, i.Username, i.Email, i.FirstName, i.LastName, i.JoinedAt
    FROM inserted AS i;
END;
GO
