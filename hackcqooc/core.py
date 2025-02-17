# -*- coding: utf-8 -*-
from hackcqooc.request import Request
from hackcqooc.user import User
from hackcqooc.msg import Msg
from hackcqooc.test import test
from hackcqooc.processor import Processor
from hackcqooc.api_url import ApiUrl

import json
import logging


class Core:
    def __init__(
        self,
        username: str = "",
        pwd: str = "",
        cookie: str = None,
        captcha: str = None,
        captcha_key: str = None,
    ) -> None:
        logging.info("Init Core")
        self.__processor = Processor()
        self.__request = Request()
        self.__api_url = ApiUrl()
        self.__user = User(username, pwd, cookie)
        self.__captcha = captcha
        self.__captcha_key = captcha_key

    def __process_user_info(self) -> None:
        id_res = self.__request.do_get(
            self.__api_url.id_api(self.__user.get_xsid())
        )
        id_data = id_res.json()
        self.__user.set_id(id_data["id"])

        info_res = self.__request.do_get(
            self.__api_url.info_api(), {"Referer": "https://www.cqooc.com/"}
        )
        info_data = info_res.json()
        self.__user.set_name(info_data["name"])
        # 如果用户使用手机号登录
        # 后续请求 API 需要网站自定义的 username
        # 所以在这里重写 username
        self.__user.set_username(info_data["username"])

    def __login_by_pwd(self) -> dict:
        api = self.__api_url.get_nonce_api()
        nonce_res = self.__request.do_get(
            api,
            {
                "Referer": "http://www.cqooc.com/login",
            },
        )
        data = nonce_res.json()
        cn = test.cnonce()
        login_hash = test.getEncodePwd(
            data["nonce"] + test.getEncodePwd(self.__user.get_pwd()) + cn
        )
        login_res = self.__request.do_post(
            self.__api_url.login_api(
                self.__user.get_username(), login_hash, data["nonce"], cn
            ),
            headers={
                "Referer": "http://www.cqooc.com/login",
            },
        )
        data = login_res.json()
        login_success = data["code"] == 0
        if login_success:
            self.__user.set_xsid(data["xsid"])
            self.__request.set_headers("Cookie", f'xsid={data["xsid"]}')
            self.__process_user_info()
            return Msg().processing("登录成功", 200, data)
        else:
            # 获取验证码
            captcha_api = self.__api_url.get_captcha_api()
            captcha_res = self.__request.do_get(
                captcha_api,
                {
                    "Referer": "http://www.cqooc.com/login",
                },
            )
            cdata = captcha_res.json()
            # return Msg().processing("登录失败，可能需要官网登录后重试", 400, data)

            return Msg().processing(
                data["msg"], 400, cdata=cdata["img"], key=cdata["key"]
            )

    def __login_by_pwd2(self, captchaToken) -> dict:
        print("pw2")
        print(captchaToken)
        api = self.__api_url.get_nonce_api()
        nonce_res = self.__request.do_get(
            api,
            {
                "Referer": "http://www.cqooc.com/login",
            },
        )
        data = nonce_res.json()
        cn = test.cnonce()
        login_hash = test.getEncodePwd(
            data["nonce"] + test.getEncodePwd(self.__user.get_pwd()) + cn
        )

        againlogin_post_data = self.__processor.process_againlogin_data(
            "1", self.__user.get_username()
        )
        login_res = self.__request.do_post(
            self.__api_url.login_api2(
                self.__user.get_username(),
                login_hash,
                data["nonce"],
                cn,
                captchaToken=captchaToken,
            ),
            data=json.dumps(againlogin_post_data),
            headers={
                "Referer": "http://www.cqooc.com/login",
            },
        )
        data = login_res.json()
        print(data)
        login_success = data["code"] == 0
        if login_success:
            self.__user.set_xsid(data["xsid"])
            self.__request.set_headers("Cookie", f'xsid={data["xsid"]}')
            self.__process_user_info()
            return Msg().processing("登录成功", 200, data)
        else:
            # 获取验证码
            captcha_api = self.__api_url.get_captcha_api()
            captcha_res = self.__request.do_get(
                captcha_api,
                {
                    "Referer": "http://www.cqooc.com/login",
                },
            )
            cdata = captcha_res.json()
            # return Msg().processing("登录失败，可能需要官网登录后重试", 400, data)

            return Msg().processing(
                data["msg"], 400, cdata=cdata["img"], key=cdata["key"]
            )

    def __login_by_cookie(self) -> dict:
        cookie = self.__user.get_cookie()
        # parse cookie to dict
        cookie_dict = dict(
            item.split("=") if "=" in item else ""
            for item in cookie.split(";")
        )
        cookie = "; ".join(
            [f"{key}={value}" for key, value in cookie_dict.items()]
        )
        self.__user.set_xsid(cookie_dict["xsid"])
        self.__request.set_headers("Cookie", cookie)
        try:
            self.__process_user_info()
        except KeyError:
            return Msg().processing("登录失败，可能需要官网登录后重试", 400)
        else:
            return Msg().processing("登录成功", 200)

    def login(self) -> dict:
        return (
            self.__login_by_pwd()
            if self.__user.get_cookie() is None
            else self.__login_by_cookie()
        )

    def get_captchaToken(self) -> dict:
        captcha_post_data = self.__processor.process_captcha_data(
            self.__captcha, self.__captcha_key
        )
        get_captchaToken_url = self.__api_url.get_captchaToken_api()
        get_captchaToken_res = self.__request.do_post(
            get_captchaToken_url,
            data=json.dumps(captcha_post_data),
            headers={
                "Referer": "http://www.cqooc.com/login",
            },
        ).json()
        print(get_captchaToken_res)
        if str(get_captchaToken_res["code"]) == "0":
            loginagainres = self.__login_by_pwd2(
                captchaToken=get_captchaToken_res["captchaToken"]
            )

            return loginagainres
        elif str(get_captchaToken_res["code"]) == "1":
            # 验证码出错重新获取验证码
            captcha_api = self.__api_url.get_captcha_api()
            captcha_res = self.__request.do_get(
                captcha_api,
                {
                    "Referer": "http://www.cqooc.com/login",
                },
            )
            cdata = captcha_res.json()
            # return Msg().processing("登录失败，可能需要官网登录后重试", 400, data)

            return Msg().processing(
                code="1", msg="验证码出错", cdata=cdata["img"], key=cdata["key"]
            )
            return {"code": "1", "msg": "invalid captcha"}

    def get_user_info(self) -> dict:
        return Msg().processing("登录成功", 200, self.__user.get_info())

    def get_course(self, limit: int = 20) -> dict:
        course_res = self.__request.do_get(
            self.__api_url.course_api(self.__user.get_id(), limit),
            headers={
                "Referer": "http://www.cqooc.com/my/learn",
                "Host": "www.cqooc.com",
            },
        )
        course_data = self.__processor.process_course_data(course_res)
        self.__user.set_course_data(course_data.copy())
        return Msg().processing("获取课程成功", 200, self.__user.get_course_data())

    def get_course_lessons(self, course_id: str) -> dict:
        mcs_id_res = self.__request.do_get(
            self.__api_url.mcs_id_api(self.__user.get_id(), course_id),
            headers={
                "Referer": "http://www.cqooc.com/my/learn",
                "Host": "www.cqooc.com",
            },
        )
        mcs_id_data = mcs_id_res.json()
        self.__user.set_mcs_id(mcs_id_data["data"][0]["id"])
        lessons_res, lessons_res_meta, lessons_status_res, count = (
            [],
            None,
            [],
            0,
        )
        while True:
            temp = self.__request.do_get(
                self.__api_url.lessons_api(course_id, start=count * 100 + 1),
                headers={
                    "Referer": "http://www.cqooc.com/learn"
                    + f"/mooc/structure?id={course_id}",
                    "host": "www.cqooc.com",
                },
            ).json()
            lessons_res_meta = temp["meta"]
            lessons_res.extend(temp["data"])
            count += 1
            if len(temp["data"]) < 100:
                break
        count = 0
        while True:
            temp = self.__request.do_get(
                self.__api_url.lessons_status_api(
                    course_id,
                    self.__user.get_username(),
                    start=count * 100 + 1,
                ),
                headers={
                    "Referer": (
                        "http://www.cqooc.com/learn/mooc/progress"
                        + f"?id={course_id}"
                    ),
                    "host": "www.cqooc.com",
                },
            ).json()
            lessons_status_res.extend(temp["data"])
            count += 1
            if len(temp["data"]) < 100:
                break
        lessons_data = self.__processor.process_lessons_data(
            self.__user.get_username(),
            lessons_res_meta,
            lessons_res,
            lessons_status_res,
        )
        self.__user.set_lessons_data(lessons_data.copy())
        return Msg().processing(
            "获取课程课时成功", 200, self.__user.get_lessons_data()
        )

    def skip_section(self, section_id: str) -> dict:
        section_data = list(
            filter(
                lambda d: d["id"] == section_id,
                self.__user.get_lessons_data()["data"],
            )
        )[0]
        post_data = self.__processor.process_section_data(
            section_data, self.__user.get_mcs_id()
        )
        skip_res = self.__request.do_post(
            self.__api_url.skip_section_api(),
            data=json.dumps(post_data),
            headers={
                "Referer": "http://www.cqooc.com/learn/mooc/structure?id="
                + section_data["courseId"],
                "Host": "www.cqooc.com",
            },
        )
        status_code = skip_res.json()["code"]
        if status_code == 2:
            return Msg().processing("已经跳过该课程", 200)
        elif status_code == 0:
            return Msg().processing("跳过课程成功", 200)
        elif status_code == 1:
            return Msg().processing("非法操作", 400)
        else:
            return Msg().processing("跳过课程失败", 400)

    def get_exam_papers_info(
        self, course_id: str, start: int = 0, limit: int = 200
    ) -> dict:
        exam_papers = self.__request.do_get(
            self.__api_url.exam_papers_api(
                course_id, start=start, limit=limit
            ),
            headers={
                "Referer": "http://www.cqooc.com/my/learn",
                "Host": "www.cqooc.com",
            },
        )
        self.__user.set_exam_papers_data(exam_papers.json().copy())
        return Msg().processing(
            "获取测验列表成功", 200, self.__user.get_exam_papers_data()
        )

    def get_exams_info(
        self, course_id: str, start: int = 0, limit: int = 200
    ) -> dict:
        exams = self.__request.do_get(
            self.__api_url.exams_api(course_id, start=start, limit=limit),
            headers={
                "Referer": "http://www.cqooc.com/learn"
                + f"/mooc/structure?id={course_id}",
                "Host": "www.cqooc.com",
            },
        )
        self.__user.set_exams_data(exams.json().copy())
        return Msg().processing("获取考试列表成功", 200, self.__user.get_exams_data())

    def get_tasks_info(
        self, course_id: str, start: int = 0, limit: int = 200
    ) -> dict:
        tasks = self.__request.do_get(
            self.__api_url.tasks_api(course_id, start=start, limit=limit),
            headers={
                "Referer": "http://www.cqooc.com/my/learn",
                "Host": "www.cqooc.com",
            },
        )
        self.__user.set_tasks_data(tasks.json().copy())
        return Msg().processing("获取作业列表成功", 200, self.__user.get_tasks_data())

    def get_chapters_info(
        self, course_id: str, start: int = 0, limit: int = 200
    ) -> dict:
        chapters = self.__request.do_get(
            self.__api_url.chapters_api(course_id, start=start, limit=limit),
            headers={
                "Referer": "http://www.cqooc.com/learn"
                + f"/mooc/progress?id={course_id}",
                "Host": "www.cqooc.com",
            },
        )
        self.__user.set_chapters_data(chapters.json().copy())
        return Msg().processing(
            "获取章节列表成功", 200, self.__user.get_chapters_data()
        )
