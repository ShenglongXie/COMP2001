/* ============================================================================
   Trail App  ·  ProfileService — views
   Target      : Microsoft SQL Server 2019 / 2022 (remote instance)
   Schema      : profile
   Idempotent  : yes — CREATE OR ALTER VIEW, so re-running just refreshes them
   Requires    : sql/profile_service_schema.sql must have been run first
   ============================================================================ */

SET NOCOUNT ON;
GO

/* ---------------------------------------------------------------------------
   1. profile.vw_MemberProfile  —  the profile page itself, one row per member

   Merges six tables:
       profile.Member            identity, bio, settings, credentials
       profile.Locality          town / village
       profile.Region            county
       profile.Country           nation
       profile.MemberPreference  preferred activities (link entity)
       profile.ActivityType      activity labels
       profile.SkillLevel        skill labels
       profile.MemberFollow      follower / following counts

   Design notes
   - LEFT JOIN + OUTER APPLY everywhere: a member with no location, no
     preferences or no follows must still produce exactly one row (the ERD's
     0..1 / 0..N cardinalities), so the view never loses a profile.
   - The credential column PasswordHash is deliberately NOT projected: the
     view is the read surface for the profile page, not for authentication.
   - No ORDER BY inside the view (SQL Server does not allow it) and no
     SELECT * — the column list is the contract the API/UI codes against.
   --------------------------------------------------------------------------- */
CREATE OR ALTER VIEW profile.vw_MemberProfile
AS
SELECT
    m.MemberId,
    m.Username,
    m.FirstName + N' ' + m.LastName                                   AS FullName,
    m.Email,
    m.AvatarUrl,
    m.Bio,

    /* --- location: three-level hierarchy flattened for display --- */
    m.LocalityId,
    l.Name                                                            AS LocalityName,
    r.Name                                                            AS RegionName,
    c.Name                                                            AS NationName,
    CASE
        WHEN l.Name IS NULL THEN NULL
        WHEN r.Name IS NULL THEN l.Name
        ELSE l.Name + N', ' + r.Name + N', ' + c.Name
    END                                                               AS DisplayLocation,

    /* --- profile settings --- */
    m.PreferredUnitSystem,
    m.PreferredLanguage,
    m.ProfileVisibility,
    m.AccountStatus,
    m.JoinedAt,
    m.LastLoginAt,
    m.EmailVerifiedAt,

    /* --- preferred activities, already aggregated to one row --- */
    ISNULL(p.PreferenceCount, 0)                                      AS PreferenceCount,
    p.TopActivity,
    p.ActivityList,

    /* --- social counters ---------------------------------------------------
       Deliberately two scalar subqueries rather than one APPLY with
       SUM(CASE WHEN ... m.MemberId ...): SQL Server rejects an outer column
       reference inside an aggregate (error 8124), and each subquery is
       covered by its own index (IX_MemberFollow_FolloweeId / PK). */
    (SELECT COUNT(*) FROM profile.MemberFollow AS f
      WHERE f.FolloweeMemberId = m.MemberId)                          AS FollowerCount,
    (SELECT COUNT(*) FROM profile.MemberFollow AS f
      WHERE f.FollowerMemberId = m.MemberId)                          AS FollowingCount
FROM profile.Member AS m
LEFT JOIN profile.Locality AS l ON l.LocalityId = m.LocalityId
LEFT JOIN profile.Region   AS r ON r.RegionId   = l.RegionId
LEFT JOIN profile.Country  AS c ON c.CountryId  = r.CountryId
OUTER APPLY
(
    SELECT
        COUNT(*)                                                      AS PreferenceCount,
        MAX(CASE WHEN mp.PreferenceRank = 1 THEN aty.Label END)       AS TopActivity,
        STRING_AGG(
            aty.Label + ISNULL(N' (' + sl.Label + N')', N''),
            N', '
        ) WITHIN GROUP (ORDER BY mp.PreferenceRank)                   AS ActivityList
    FROM profile.MemberPreference AS mp
    JOIN profile.ActivityType     AS aty ON aty.ActivityTypeId = mp.ActivityTypeId
    LEFT JOIN profile.SkillLevel  AS sl  ON sl.SkillLevelId    = mp.SkillLevelId
    WHERE mp.MemberId = m.MemberId
) AS p
;
GO

/* ---------------------------------------------------------------------------
   2. profile.vw_MemberPreferenceDetail  —  supporting view for the
   "preferred activities" panel: one row per (member, activity), fully decoded
   from the link entity plus its three vocabulary tables.
   --------------------------------------------------------------------------- */
CREATE OR ALTER VIEW profile.vw_MemberPreferenceDetail
AS
SELECT
    m.MemberId,
    m.Username,
    mp.PreferenceRank,
    aty.ActivityTypeId,
    aty.Slug                                                          AS ActivitySlug,
    aty.Label                                                         AS ActivityName,
    ac.Name                                                           AS CategoryName,
    sl.SkillLevelId,
    sl.Code                                                           AS SkillCode,
    sl.Label                                                          AS SkillLabel,
    sl.MaxTrailDifficulty,
    mp.CreatedAt
FROM profile.MemberPreference AS mp
JOIN profile.Member           AS m   ON m.MemberId        = mp.MemberId
JOIN profile.ActivityType     AS aty ON aty.ActivityTypeId = mp.ActivityTypeId
JOIN profile.ActivityCategory AS ac  ON ac.CategoryId      = aty.CategoryId
LEFT JOIN profile.SkillLevel  AS sl  ON sl.SkillLevelId    = mp.SkillLevelId;
GO

/* ============================================================================
   3. VERIFICATION
   ============================================================================ */

/* 3.1 the whole profile page, one row per member */
SELECT
    MemberId,
    Username,
    FullName,
    DisplayLocation,
    PreferenceCount,
    TopActivity,
    ActivityList,
    FollowingCount AS [Following],
    FollowerCount,
    ProfileVisibility,
    AccountStatus
FROM profile.vw_MemberProfile
ORDER BY MemberId;
GO

/* 3.2 the view must not fan out: rows = rows of Member */
SELECT
    (SELECT COUNT(*) FROM profile.Member)          AS MemberRows,
    (SELECT COUNT(*) FROM profile.vw_MemberProfile) AS ViewRows,
    CASE WHEN (SELECT COUNT(*) FROM profile.Member)
            = (SELECT COUNT(*) FROM profile.vw_MemberProfile)
         THEN N'PASS: one row per member'
         ELSE N'FAIL: join duplicated rows'
    END                                            AS CardinalityCheck;
GO

/* 3.3 filter on a column that only exists after the 4-table location join */
SELECT
    NationName,
    COUNT(*) AS Members
FROM profile.vw_MemberProfile
GROUP BY NationName
ORDER BY NationName;
GO

/* 3.4 one member's profile page, the way the app would call it */
SELECT
    Username, FullName, DisplayLocation, Bio,
    ActivityList, PreferenceCount, FollowerCount, FollowingCount, JoinedAt
FROM profile.vw_MemberProfile
WHERE Username = N'megan.pryce';
GO

/* 3.5 the supporting view for the preference panel */
SELECT
    Username, PreferenceRank, ActivityName, CategoryName,
    ISNULL(SkillLabel, N'(unset)') AS SkillLabel, MaxTrailDifficulty
FROM profile.vw_MemberPreferenceDetail
WHERE Username = N'callum.fraser'
ORDER BY PreferenceRank;
GO
