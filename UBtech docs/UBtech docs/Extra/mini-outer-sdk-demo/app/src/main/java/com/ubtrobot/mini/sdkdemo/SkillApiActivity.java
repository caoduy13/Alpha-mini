package com.ubtrobot.mini.sdkdemo;

import android.support.annotation.NonNull;
import android.support.v7.app.AppCompatActivity;
import android.os.Bundle;
import android.util.Log;
import android.view.View;

import com.ubtechinc.skill.SkillApi;
import com.ubtrobot.commons.ResponseListener;

import java.util.List;

public class SkillApiActivity extends AppCompatActivity {
    List<SkillApi.SKILL_NAME> skill_types = SkillApi.get().loadAllSkills();
    private static final String TAG = "SkillApiActivity";
    int index = 0;
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_skill_api);
        findViewById(R.id.btn_test).setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                Log.i(TAG,"start " + skill_types.get(index));
                SkillApi.get().startSkill( skill_types.get(index), new ResponseListener<Void>() {
                    @Override
                    public void onResponseSuccess(Void aVoid) {
                        Log.i(TAG,"onResponseSuccess");
                    }

                    @Override
                    public void onFailure(int i, @NonNull String s) {
                        Log.i(TAG,"onFailure i = " + i);
                    }
                });
                index++;
                if(index >= skill_types.size()) {
                    index = 0;
                }

            }
        });

        findViewById(R.id.btn_startSkill).setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                DemoSkill.startThisSkill();
            }
        });

        findViewById(R.id.btn_stopSkill).setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                DemoSkill.stopThisSkill();
            }
        });
    }
}
