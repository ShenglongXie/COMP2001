SET NOCOUNT ON;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

CREATE OR ALTER PROCEDURE CW2.usp_Member_Create
    @Username     NVARCHAR(30),
    @Email        NVARCHAR(320) = NULL,
    @FirstName    NVARCHAR(60)  = NULL,
    @LastName     NVARCHAR(60)  = NULL,
    @PasswordHash VARCHAR(255)  = NULL,
    @LocalityId   INT           = NULL,
    @MemberId     BIGINT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO CW2.Member (Username, Email, FirstName, LastName, PasswordHash, LocalityId)
    VALUES (@Username, @Email, @FirstName, @LastName, @PasswordHash, @LocalityId);

    SET @MemberId = CAST(SCOPE_IDENTITY() AS BIGINT);
END;
GO

CREATE OR ALTER PROCEDURE CW2.usp_Member_Get
    @MemberId BIGINT
AS
BEGIN
    SET NOCOUNT ON;

    SELECT MemberId, Username, FullName, Email, DisplayLocation,
           PreferredUnitSystem, PreferredLanguage, ProfileVisibility, AccountStatus,
           PreferenceCount, FollowerCount, FollowingCount, JoinedAt
    FROM CW2.vw_MemberProfile
    WHERE MemberId = @MemberId;
END;
GO

CREATE OR ALTER PROCEDURE CW2.usp_Member_List
    @Limit  INT = 20,
    @Offset INT = 0
AS
BEGIN
    SET NOCOUNT ON;

    SELECT MemberId, Username, FullName, DisplayLocation, AccountStatus, JoinedAt
    FROM CW2.vw_MemberProfile
    ORDER BY MemberId
    OFFSET @Offset ROWS FETCH NEXT @Limit ROWS ONLY;
END;
GO

CREATE OR ALTER PROCEDURE CW2.usp_Member_Update
    @MemberId      BIGINT,
    @Username      NVARCHAR(30) = NULL,
    @Email         NVARCHAR(320) = NULL,
    @FirstName     NVARCHAR(60) = NULL,
    @LastName      NVARCHAR(60) = NULL,
    @Bio           NVARCHAR(500) = NULL,
    @LocalityId    INT = NULL,
    @AccountStatus VARCHAR(12) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE CW2.Member
       SET Username      = COALESCE(@Username, Username),
           Email         = COALESCE(@Email, Email),
           FirstName     = COALESCE(@FirstName, FirstName),
           LastName      = COALESCE(@LastName, LastName),
           Bio           = COALESCE(@Bio, Bio),
           LocalityId    = COALESCE(@LocalityId, LocalityId),
           AccountStatus = COALESCE(@AccountStatus, AccountStatus),
           UpdatedAt     = SYSUTCDATETIME()
     WHERE MemberId = @MemberId;

    SELECT @@ROWCOUNT AS RowsAffected;
END;
GO

CREATE OR ALTER PROCEDURE CW2.usp_Member_Delete
    @MemberId BIGINT
AS
BEGIN
    SET NOCOUNT ON;

    DELETE FROM CW2.Member
     WHERE MemberId = @MemberId;

    SELECT @@ROWCOUNT AS RowsAffected;
END;
GO
