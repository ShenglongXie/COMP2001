-- Recreates the tables and demo data; existing table data will be lost.

SET NOCOUNT ON;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- Schema
IF SCHEMA_ID('CW1') IS NULL
    EXEC ('CREATE SCHEMA CW1 AUTHORIZATION dbo;');
GO

-- Remove existing objects
IF OBJECT_ID('CW1.vw_MemberPreferenceDetail', 'V') IS NOT NULL DROP VIEW CW1.vw_MemberPreferenceDetail;
IF OBJECT_ID('CW1.vw_MemberProfile', 'V') IS NOT NULL DROP VIEW CW1.vw_MemberProfile;
IF OBJECT_ID('CW1.MemberPreference', 'U') IS NOT NULL DROP TABLE CW1.MemberPreference;
IF OBJECT_ID('CW1.MemberFollow',     'U') IS NOT NULL DROP TABLE CW1.MemberFollow;
IF OBJECT_ID('CW1.Member',           'U') IS NOT NULL DROP TABLE CW1.Member;
IF OBJECT_ID('CW1.ActivityType',     'U') IS NOT NULL DROP TABLE CW1.ActivityType;
IF OBJECT_ID('CW1.ActivityCategory', 'U') IS NOT NULL DROP TABLE CW1.ActivityCategory;
IF OBJECT_ID('CW1.SkillLevel',       'U') IS NOT NULL DROP TABLE CW1.SkillLevel;
IF OBJECT_ID('CW1.Locality',         'U') IS NOT NULL DROP TABLE CW1.Locality;
IF OBJECT_ID('CW1.Region',           'U') IS NOT NULL DROP TABLE CW1.Region;
IF OBJECT_ID('CW1.Country',          'U') IS NOT NULL DROP TABLE CW1.Country;
GO

-- Tables
CREATE TABLE CW1.Country
(
    CountryId   SMALLINT      NOT NULL,
    IsoCode     CHAR(6)       NOT NULL,
    Name        NVARCHAR(80)  NOT NULL,
    CONSTRAINT PK_Country        PRIMARY KEY (CountryId),
    CONSTRAINT UQ_Country_IsoCode UNIQUE (IsoCode),
    CONSTRAINT UQ_Country_Name    UNIQUE (Name),
    CONSTRAINT CK_Country_IsoCode CHECK (IsoCode LIKE 'GB-[A-Z][A-Z][A-Z]')
);
GO

CREATE TABLE CW1.Region
(
    RegionId    INT           NOT NULL,
    CountryId   SMALLINT      NOT NULL,
    GssCode     CHAR(9)       NOT NULL,
    Name        NVARCHAR(120) NOT NULL,
    CONSTRAINT PK_Region          PRIMARY KEY (RegionId),
    CONSTRAINT UQ_Region_GssCode  UNIQUE (CountryId, GssCode),
    CONSTRAINT CK_Region_GssCode  CHECK (GssCode LIKE '[EWSN][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'),
    CONSTRAINT FK_Region_Country  FOREIGN KEY (CountryId)
        REFERENCES CW1.Country (CountryId) ON DELETE NO ACTION
);
GO

CREATE TABLE CW1.Locality
(
    LocalityId  INT           NOT NULL,
    RegionId    INT           NOT NULL,
    Name        NVARCHAR(120) NOT NULL,
    CONSTRAINT PK_Locality          PRIMARY KEY (LocalityId),
    CONSTRAINT UQ_Locality_Name     UNIQUE (RegionId, Name),
    CONSTRAINT FK_Locality_Region   FOREIGN KEY (RegionId)
        REFERENCES CW1.Region (RegionId) ON DELETE NO ACTION
);
GO

CREATE TABLE CW1.ActivityCategory
(
    CategoryId  SMALLINT      NOT NULL,
    Name        VARCHAR(24)   NOT NULL,
    Description NVARCHAR(120) NULL,
    CONSTRAINT PK_ActivityCategory      PRIMARY KEY (CategoryId),
    CONSTRAINT UQ_ActivityCategory_Name UNIQUE (Name)
);
GO

CREATE TABLE CW1.ActivityType
(
    ActivityTypeId  SMALLINT      NOT NULL,
    CategoryId      SMALLINT      NOT NULL,
    Slug            VARCHAR(24)   NOT NULL,
    Label           NVARCHAR(40)  NOT NULL,
    IsActive        BIT           NOT NULL CONSTRAINT DF_ActivityType_Active DEFAULT (1),
    CONSTRAINT PK_ActivityType        PRIMARY KEY (ActivityTypeId),
    CONSTRAINT UQ_ActivityType_Slug   UNIQUE (Slug),
    CONSTRAINT FK_ActivityType_Category FOREIGN KEY (CategoryId)
        REFERENCES CW1.ActivityCategory (CategoryId) ON DELETE NO ACTION
);
GO

CREATE TABLE CW1.SkillLevel
(
    SkillLevelId        SMALLINT     NOT NULL,
    Code                VARCHAR(16)  NOT NULL,
    Label               NVARCHAR(24) NOT NULL,
    MaxTrailDifficulty  TINYINT      NOT NULL,
    CONSTRAINT PK_SkillLevel          PRIMARY KEY (SkillLevelId),
    CONSTRAINT UQ_SkillLevel_Code     UNIQUE (Code),
    CONSTRAINT CK_SkillLevel_MaxDiff  CHECK (MaxTrailDifficulty BETWEEN 1 AND 5)
);
GO

CREATE TABLE CW1.Member
(
    MemberId             BIGINT        IDENTITY(1,1) NOT NULL,
    Username             NVARCHAR(30)  COLLATE Latin1_General_100_CI_AS NOT NULL,
    Email                NVARCHAR(320) COLLATE Latin1_General_100_CI_AS NULL,
    FirstName            NVARCHAR(60)  NULL,
    LastName             NVARCHAR(60)  NULL,
    AvatarUrl            NVARCHAR(400) NULL,
    Bio                  NVARCHAR(500) NULL,
    LocalityId           INT           NULL,
    PreferredUnitSystem  VARCHAR(8)    NOT NULL CONSTRAINT DF_Member_UnitSystem DEFAULT ('metric'),
    PreferredLanguage    CHAR(5)       NOT NULL CONSTRAINT DF_Member_Language   DEFAULT ('en-GB'),
    ProfileVisibility    VARCHAR(10)   NOT NULL CONSTRAINT DF_Member_Visibility DEFAULT ('public'),
    AccountStatus        VARCHAR(12)   NOT NULL CONSTRAINT DF_Member_Status     DEFAULT ('active'),
    PasswordHash         VARCHAR(255)  NULL,
    EmailVerifiedAt      DATETIME2(0)  NULL,
    LastLoginAt          DATETIME2(0)  NULL,
    JoinedAt             DATETIME2(0)  NOT NULL CONSTRAINT DF_Member_JoinedAt   DEFAULT (SYSUTCDATETIME()),
    UpdatedAt            DATETIME2(0)  NOT NULL CONSTRAINT DF_Member_UpdatedAt  DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT PK_Member              PRIMARY KEY (MemberId),
    CONSTRAINT UQ_Member_Username     UNIQUE (Username),
    CONSTRAINT CK_Member_UnitSystem   CHECK (PreferredUnitSystem IN ('metric', 'imperial')),
    CONSTRAINT CK_Member_Visibility   CHECK (ProfileVisibility IN ('public', 'followers', 'private')),
    CONSTRAINT CK_Member_Status       CHECK (AccountStatus IN ('active', 'suspended', 'deactivated')),
    CONSTRAINT FK_Member_Locality     FOREIGN KEY (LocalityId)
        REFERENCES CW1.Locality (LocalityId) ON DELETE SET NULL
);
GO

CREATE TABLE CW1.MemberPreference
(
    MemberId        BIGINT       NOT NULL,
    ActivityTypeId  SMALLINT     NOT NULL,
    PreferenceRank  SMALLINT     NOT NULL,
    SkillLevelId    SMALLINT     NULL,
    CreatedAt       DATETIME2(0) NOT NULL CONSTRAINT DF_MemberPreference_CreatedAt DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT PK_MemberPreference       PRIMARY KEY (MemberId, ActivityTypeId),
    CONSTRAINT UQ_MemberPreference_Rank  UNIQUE (MemberId, PreferenceRank),
    CONSTRAINT CK_MemberPreference_Rank  CHECK (PreferenceRank BETWEEN 1 AND 20),
    CONSTRAINT FK_MemberPreference_Member FOREIGN KEY (MemberId)
        REFERENCES CW1.Member (MemberId) ON DELETE CASCADE,
    CONSTRAINT FK_MemberPreference_Type   FOREIGN KEY (ActivityTypeId)
        REFERENCES CW1.ActivityType (ActivityTypeId) ON DELETE NO ACTION,
    CONSTRAINT FK_MemberPreference_Skill  FOREIGN KEY (SkillLevelId)
        REFERENCES CW1.SkillLevel (SkillLevelId) ON DELETE SET NULL
);
GO

CREATE TABLE CW1.MemberFollow
(
    FollowerMemberId  BIGINT       NOT NULL,
    FolloweeMemberId  BIGINT       NOT NULL,
    FollowedAt        DATETIME2(0) NOT NULL CONSTRAINT DF_MemberFollow_At DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT PK_MemberFollow        PRIMARY KEY (FollowerMemberId, FolloweeMemberId),
    CONSTRAINT CK_MemberFollow_NoSelf CHECK (FollowerMemberId <> FolloweeMemberId),
    CONSTRAINT FK_MemberFollow_Follower FOREIGN KEY (FollowerMemberId)
        REFERENCES CW1.Member (MemberId) ON DELETE NO ACTION,
    CONSTRAINT FK_MemberFollow_Followee FOREIGN KEY (FolloweeMemberId)
        REFERENCES CW1.Member (MemberId) ON DELETE NO ACTION
);
GO

-- Indexes
CREATE INDEX IX_Region_CountryId            ON CW1.Region (CountryId);
CREATE INDEX IX_Locality_RegionId           ON CW1.Locality (RegionId);
CREATE INDEX IX_ActivityType_CategoryId     ON CW1.ActivityType (CategoryId);
CREATE UNIQUE INDEX UQ_Member_Email         ON CW1.Member (Email) WHERE Email IS NOT NULL;
CREATE INDEX IX_Member_LocalityId           ON CW1.Member (LocalityId);
CREATE INDEX IX_MemberPreference_TypeId     ON CW1.MemberPreference (ActivityTypeId) INCLUDE (MemberId);
CREATE INDEX IX_MemberPreference_SkillLevel ON CW1.MemberPreference (SkillLevelId) INCLUDE (MemberId);
CREATE INDEX IX_MemberFollow_FolloweeId     ON CW1.MemberFollow (FolloweeMemberId) INCLUDE (FollowerMemberId);
GO

-- Demo data
INSERT INTO CW1.Country (CountryId, IsoCode, Name) VALUES
    (1, 'GB-ENG', N'England'),
    (2, 'GB-SCT', N'Scotland'),
    (3, 'GB-WLS', N'Wales'),
    (4, 'GB-NIR', N'Northern Ireland');
GO

INSERT INTO CW1.Region (RegionId, CountryId, GssCode, Name) VALUES
    (1, 1, 'E10000007', N'Derbyshire'),
    (2, 1, 'E10000006', N'Cumbria'),
    (3, 1, 'E10000023', N'North Yorkshire'),
    (4, 2, 'S12000017', N'Highland'),
    (5, 2, 'S12000035', N'Argyll and Bute'),
    (6, 3, 'W06000002', N'Gwynedd'),
    (7, 3, 'W06000009', N'Pembrokeshire'),
    (8, 4, 'N09000010', N'County Down');
GO

INSERT INTO CW1.Locality (LocalityId, RegionId, Name) VALUES
    (1,  1, N'Bakewell'),
    (2,  1, N'Castleton'),
    (3,  2, N'Keswick'),
    (4,  2, N'Ambleside'),
    (5,  3, N'Hawes'),
    (6,  4, N'Aviemore'),
    (7,  5, N'Oban'),
    (8,  6, N'Betws-y-Coed'),
    (9,  7, N'Tenby'),
    (10, 8, N'Newcastle');
GO

INSERT INTO CW1.ActivityCategory (CategoryId, Name, Description) VALUES
    (1, 'foot',  N'Activities travelled on foot'),
    (2, 'wheel', N'Activities travelled on wheels'),
    (3, 'water', N'Activities on the water');
GO

INSERT INTO CW1.ActivityType (ActivityTypeId, CategoryId, Slug, Label, IsActive) VALUES
    (1, 1, 'walking',       N'Walking',       1),
    (2, 1, 'hiking',        N'Hiking',        1),
    (3, 1, 'trail-running', N'Trail Running', 1),
    (4, 2, 'cycling',       N'Cycling',       1),
    (5, 3, 'kayaking',      N'Kayaking',      0);
GO

INSERT INTO CW1.SkillLevel (SkillLevelId, Code, Label, MaxTrailDifficulty) VALUES
    (1, 'beginner',     N'Beginner',     2),
    (2, 'intermediate', N'Intermediate', 3),
    (3, 'advanced',     N'Advanced',     4),
    (4, 'expert',       N'Expert',       5);
GO

SET IDENTITY_INSERT CW1.Member ON;
INSERT INTO CW1.Member
    (MemberId, Username, Email, FirstName, LastName, AvatarUrl, Bio, LocalityId,
     PreferredUnitSystem, PreferredLanguage, ProfileVisibility, AccountStatus,
     PasswordHash, EmailVerifiedAt, LastLoginAt, JoinedAt, UpdatedAt)
VALUES
    (1, N'rowan.ashby', N'rowan.ashby@example.org', N'Rowan', N'Ashby',
     N'https://cdn.trail.example/avatars/rowan.jpg',
     N'Weekend walker, happiest on a limestone dale.', 1,
     'metric', 'en-GB', 'public', 'active',
     'AQAAAAIAAYagAAAAEExampleHashRowan01', '2025-03-04T10:12:00', '2026-11-09T07:41:00',
     '2025-03-04T10:12:00', '2026-11-09T07:41:00'),
    (2, N'megan.pryce', N'megan.pryce@example.org', N'Megan', N'Pryce',
     NULL, N'Slate country local; Welsh is my first language.', 8,
     'metric', 'cy-GB', 'followers', 'active',
     'AQAAAAIAAYagAAAAEExampleHashMegan02', '2025-04-18T16:30:00', '2026-11-07T18:05:00',
     '2025-04-18T16:30:00', '2026-11-07T18:05:00'),
    (3, N'callum.fraser', N'callum.fraser@example.org', N'Callum', N'Fraser',
     N'https://cdn.trail.example/avatars/callum.jpg',
     N'Munro bagger and trail runner.', 6,
     'imperial', 'en-GB', 'public', 'active',
     'AQAAAAIAAYagAAAAEExampleHashCallum03', '2024-11-02T09:00:00', '2026-11-10T06:15:00',
     '2024-11-02T09:00:00', '2026-11-10T06:15:00'),
    (4, N'freya.whitlock', N'freya.whitlock@example.org', N'Freya', N'Whitlock',
     NULL, N'Prefers a gentle lakeside stroll with a flask of tea.', 3,
     'metric', 'en-GB', 'public', 'active',
     'AQAAAAIAAYagAAAAEExampleHashFreya04', '2025-06-21T11:45:00', '2026-11-05T09:20:00',
     '2025-06-21T11:45:00', '2026-11-05T09:20:00'),
    (5, N'tomasz.nowak', N'tomasz.nowak@example.org', N'Tomasz', N'Nowak',
     NULL, NULL, NULL,
     'metric', 'en-GB', 'private', 'active',
     'AQAAAAIAAYagAAAAEExampleHashTomasz05', NULL, '2026-11-01T20:10:00',
     '2026-10-28T20:10:00', '2026-11-01T20:10:00'),
    (6, N'aisha.rahman', N'aisha.rahman@example.org', N'Aisha', N'Rahman',
     N'https://cdn.trail.example/avatars/aisha.jpg',
     N'Castleton-based, collecting ridge walks.', 2,
     'metric', 'en-GB', 'public', 'active',
     'AQAAAAIAAYagAAAAEExampleHashAisha06', '2025-01-15T08:05:00', '2026-11-08T12:33:00',
     '2025-01-15T08:05:00', '2026-11-08T12:33:00'),
    (7, N'dylan.morgan', N'dylan.morgan@example.org', N'Dylan', N'Morgan',
     NULL, N'Coastal path completer, slowly.', 9,
     'imperial', 'en-GB', 'public', 'active',
     'AQAAAAIAAYagAAAAEExampleHashDylan07', '2025-02-09T14:20:00', '2026-11-04T17:48:00',
     '2025-02-09T14:20:00', '2026-11-04T17:48:00'),
    (8, N'niamh.kelly', N'niamh.kelly@example.org', N'Niamh', N'Kelly',
     NULL, N'Mourne rambler.', 10,
     'metric', 'en-GB', 'followers', 'active',
     'AQAAAAIAAYagAAAAEExampleHashNiamh08', '2025-05-30T19:00:00', '2026-11-06T08:02:00',
     '2025-05-30T19:00:00', '2026-11-06T08:02:00'),
    (9, N'harriet.vale', N'harriet.vale@example.org', N'Harriet', N'Vale',
     N'https://cdn.trail.example/avatars/harriet.jpg',
     N'Volunteer path warden around Ambleside.', 4,
     'metric', 'en-GB', 'public', 'active',
     'AQAAAAIAAYagAAAAEExampleHashHarriet09', '2024-08-12T07:30:00', '2026-11-10T05:55:00',
     '2024-08-12T07:30:00', '2026-11-10T05:55:00'),
    (10, N'owen.bevan', N'owen.bevan@example.org', N'Owen', N'Bevan',
     NULL, N'Account under review.', 7,
     'metric', 'en-GB', 'private', 'suspended',
     'AQAAAAIAAYagAAAAEExampleHashOwen10', '2025-09-01T12:00:00', '2026-10-20T15:10:00',
     '2025-09-01T12:00:00', '2026-10-20T15:10:00');
SET IDENTITY_INSERT CW1.Member OFF;
GO

DBCC CHECKIDENT ('CW1.Member', RESEED);
GO

INSERT INTO CW1.MemberPreference (MemberId, ActivityTypeId, PreferenceRank, SkillLevelId) VALUES
    (1, 1, 1, 2), (1, 2, 2, 2), (1, 4, 3, 1),
    (2, 2, 1, 3), (2, 1, 2, 1),
    (3, 2, 1, 4), (3, 3, 2, 3), (3, 4, 3, 2),
    (4, 1, 1, 1), (4, 3, 2, 2),
    (6, 2, 1, 2), (6, 4, 2, 1),
    (7, 4, 1, 3), (7, 1, 2, 2),
    (8, 1, 1, 2), (8, 2, 2, 2), (8, 3, 3, 1),
    (9, 2, 1, 3),
    (10, 1, 1, 1);
GO

INSERT INTO CW1.MemberFollow (FollowerMemberId, FolloweeMemberId, FollowedAt) VALUES
    (1, 2, '2025-05-01T09:00:00'),
    (1, 4, '2025-07-14T18:20:00'),
    (2, 1, '2025-05-02T08:10:00'),
    (3, 1, '2025-08-03T07:45:00'),
    (4, 1, '2025-07-15T19:00:00'),
    (6, 2, '2025-09-09T10:30:00'),
    (7, 3, '2025-10-11T06:50:00'),
    (8, 6, '2026-01-20T13:15:00'),
    (9, 1, '2024-09-01T11:00:00'),
    (9, 4, '2024-09-01T11:02:00');
GO

-- Verification queries
DECLARE @sql NVARCHAR(MAX) = N'';

SELECT @sql = STRING_AGG(
           CAST('SELECT N''' + s.name + '.' + t.name + ''' AS TableName, COUNT_BIG(*) AS [Rows] FROM '
                + QUOTENAME(s.name) + '.' + QUOTENAME(t.name) AS NVARCHAR(MAX)),
           N' UNION ALL ')
FROM sys.tables AS t
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
WHERE s.name = 'CW1';

SET @sql = N'SELECT TableName, [Rows] FROM (' + @sql + N') AS counts ORDER BY TableName;';

EXEC sys.sp_executesql @sql;
GO

SELECT
    m.MemberId,
    m.Username,
    m.FirstName + N' ' + m.LastName                AS FullName,
    ISNULL(l.Name, N'(not set)')                   AS Locality,
    ISNULL(r.Name, N'(not set)')                   AS Region,
    ISNULL(c.Name, N'(not set)')                   AS Nation,
    m.PreferredUnitSystem,
    m.PreferredLanguage,
    m.ProfileVisibility,
    m.AccountStatus,
    (SELECT COUNT(*) FROM CW1.MemberPreference p WHERE p.MemberId = m.MemberId)        AS Preferences,
    (SELECT COUNT(*) FROM CW1.MemberFollow f WHERE f.FollowerMemberId = m.MemberId)    AS [Following],
    (SELECT COUNT(*) FROM CW1.MemberFollow f WHERE f.FolloweeMemberId = m.MemberId)    AS Followers,
    m.JoinedAt
FROM CW1.Member AS m
LEFT JOIN CW1.Locality AS l ON l.LocalityId = m.LocalityId
LEFT JOIN CW1.Region   AS r ON r.RegionId   = l.RegionId
LEFT JOIN CW1.Country  AS c ON c.CountryId  = r.CountryId
ORDER BY m.MemberId;
GO

SELECT
    m.Username,
    p.PreferenceRank,
    act.Label                    AS Activity,
    ac.Name                      AS Category,
    ISNULL(sl.Label, N'(unset)') AS SkillLevel,
    sl.MaxTrailDifficulty,
    p.CreatedAt
FROM CW1.MemberPreference AS p
JOIN CW1.Member           AS m   ON m.MemberId        = p.MemberId
JOIN CW1.ActivityType     AS act ON act.ActivityTypeId = p.ActivityTypeId
JOIN CW1.ActivityCategory AS ac  ON ac.CategoryId      = act.CategoryId
LEFT JOIN CW1.SkillLevel  AS sl  ON sl.SkillLevelId    = p.SkillLevelId
ORDER BY m.Username, p.PreferenceRank;
GO

SELECT
    f.FollowerMemberId,
    fol.Username AS Follower,
    f.FolloweeMemberId,
    fee.Username AS Followee,
    f.FollowedAt
FROM CW1.MemberFollow AS f
JOIN CW1.Member AS fol ON fol.MemberId = f.FollowerMemberId
JOIN CW1.Member AS fee ON fee.MemberId = f.FolloweeMemberId
ORDER BY f.FollowerMemberId, f.FolloweeMemberId;
GO

SELECT
    c.Name           AS Nation,
    r.Name           AS Region,
    l.Name           AS Locality,
    COUNT(m.MemberId) AS Members
FROM CW1.Country  AS c
LEFT JOIN CW1.Region   AS r ON r.CountryId  = c.CountryId
LEFT JOIN CW1.Locality AS l ON l.RegionId   = r.RegionId
LEFT JOIN CW1.Member   AS m ON m.LocalityId = l.LocalityId
GROUP BY c.Name, r.Name, l.Name
ORDER BY c.Name, r.Name, l.Name;
GO

SELECT
    N'all 9 tables populated' AS CheckName,
    CASE WHEN MIN(cnt) > 0 THEN N'PASS' ELSE N'FAIL' END AS Result
FROM (
    SELECT COUNT(*) AS cnt FROM CW1.Country
    UNION ALL SELECT COUNT(*) FROM CW1.Region
    UNION ALL SELECT COUNT(*) FROM CW1.Locality
    UNION ALL SELECT COUNT(*) FROM CW1.ActivityCategory
    UNION ALL SELECT COUNT(*) FROM CW1.ActivityType
    UNION ALL SELECT COUNT(*) FROM CW1.SkillLevel
    UNION ALL SELECT COUNT(*) FROM CW1.Member
    UNION ALL SELECT COUNT(*) FROM CW1.MemberPreference
    UNION ALL SELECT COUNT(*) FROM CW1.MemberFollow
) AS per_table;
GO
